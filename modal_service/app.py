"""Modal deployment entrypoint for the GRU Mascot service.

Firebase Authentication authenticates every cost-bearing request. The Android
client never receives a Modal account or proxy credential.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import shutil
import secrets
import time
from dataclasses import asdict
from pathlib import Path
import modal
from pydantic import BaseModel, ConfigDict, Field

from modal_service.catalog import POSE_PROMPT_VERSION
from modal_service.config import generation_enabled, limits_for, required_environment
from modal_service.coordinator import JobCoordinator, JobOperation, owner_counter_id
from modal_service.costs import CostLimitExceeded, RateLimitExceeded
from modal_service.domain import DomainError, JobNotFound, JobRecord, JobState
from modal_service.health import generation_payload, live_payload, ready_payload
from modal_service.observability import log_event
from modal_service.outbox import due_files, enqueue, load, pending_count, record_failure
from modal_service.rate_limits import consume_limit
from modal_service.request_validation import validate_idempotency_key
from modal_service.retention import delete_job_assets, purge_expired_originals, purge_expired_temporary_assets
from modal_service.security import AuthenticationRejected, app_check_token, bearer_token, may_schedule_gpu, valid_firebase_claims
from modal_service.telemetry import generation_event
from modal_service.validation import ImageValidationError, validate_image

APP_NAME = "gru-mascot"
FIREBASE_PROJECT_ID = "gru-mascote"
FIREBASE_PROJECT_NUMBER = "816774877835"
ASSET_ROOT = "/gru-assets"
MODEL_ROOT = "/gru-models"
TELEMETRY_ROOT = "/gru-telemetry/outbox"
CONSENT_POLICY_VERSION = "image-processing-v1"
MAX_REQUEST_BODY_BYTES = 14_500_000
ENVIRONMENT = required_environment(os.getenv("GRU_MASCOT_ENV"))
LIMITS = limits_for(ENVIRONMENT)
GPU_GENERATION_ENABLED = generation_enabled(ENVIRONMENT, os.getenv("GPU_GENERATION_ENABLED"))
MASTER_GPU = "H100"
QWEN_MODEL_ID = "Qwen/Qwen-Image-Edit-2511"
QWEN_MODEL_REVISION = "6f3ccc0b56e431dc6a0c2b2039706d7d26f22cb9"
LIGHTNING_MODEL_ID = "lightx2v/Qwen-Image-Edit-2511-Lightning"
LIGHTNING_MODEL_REVISION = "d74eba145674fd7e31b949324e148e21e7118abd"
LIGHTNING_WEIGHT = "Qwen-Image-Edit-2511-Lightning-4steps-V1.0-fp32.safetensors"


class CreateJobRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    image_base64: str = Field(min_length=1, max_length=14_000_000)
    content_type: str | None = None
    consent_policy_version: str = Field(pattern=r"^[A-Za-z0-9._-]{1,64}$")


class ApproveMasterRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    master_id: str = Field(pattern=r"^master_[1-4]$")


class PoseRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    pose_id: str = Field(pattern=r"^pose_[0-9]{2}$")

api_image = (
    modal.Image.debian_slim(python_version="3.12")
    .env(
        {
            "GRU_MASCOT_ENV": ENVIRONMENT.value,
            "GPU_GENERATION_ENABLED": "true" if GPU_GENERATION_ENABLED else "false",
            "MODAL_GPU_HOURLY_USD": os.getenv("MODAL_GPU_HOURLY_USD", ""),
        }
    )
    .pip_install(
        "fastapi[standard]==0.141.1",
        "starlette==1.6.0",
        "pillow==12.3.0",
        "httpx==0.28.1",
        "PyJWT==2.10.1",
        "google-auth==2.40.3",
        "firebase-admin==6.9.0",
    )
)
gpu_image = api_image.pip_install(
    "torch==2.6.0",
    "torchvision==0.21.0",
    # Qwen-Image-Edit-2511 declares QwenImageEditPlusPipeline, introduced
    # in diffusers 0.36. Pin the first compatible release rather than
    # accepting a moving dependency at GPU-container build time.
    "diffusers==0.36.0",
    # The 2511 model configuration uses the newer Qwen 2.5-VL schema;
    # 4.51 leaves nested decoder_config as a dict during pipeline loading.
    "transformers==4.57.6",
    "accelerate==1.6.0",
    "peft==0.17.1",
    "safetensors==0.5.3",
    "numpy==2.2.6",
)
app = modal.App(APP_NAME)
assets = modal.Volume.from_name("gru-mascot-assets", create_if_missing=True)
models = modal.Volume.from_name("gru-mascot-models", create_if_missing=True)
jobs = modal.Dict.from_name("gru-mascot-jobs", create_if_missing=True)
idempotency = modal.Dict.from_name("gru-mascot-idempotency", create_if_missing=True)
usage = modal.Dict.from_name("gru-mascot-usage", create_if_missing=True)
operations = modal.Dict.from_name("gru-mascot-operations", create_if_missing=True)
telemetry_volume = modal.Volume.from_name("gru-mascot-telemetry", create_if_missing=True)
firebase_admin_secret = modal.Secret.from_name("gru-mascot-firebase-admin")
web_bff_jwt_secret = modal.Secret.from_name("gru-mascot-bff-jwt")
telemetry_secret = modal.Secret.from_name("gru-mascot-supabase-telemetry")


def _record_key(user_id: str, idempotency_key: str) -> str:
    return f"create:{user_id}:{idempotency_key}"


def _operation_key(user_id: str, operation: str) -> str:
    return f"operation:{user_id}:{operation}"


def _asset_path(job_id: str, folder: str, name: str) -> Path:
    return Path(ASSET_ROOT, folder, job_id, name)


def _templates_installed() -> bool:
    pointer = Path(ASSET_ROOT, "pose_templates", "active.json")
    if not pointer.is_file():
        return False
    try:
        version = str(json.loads(pointer.read_text(encoding="utf-8"))["version"])
    except (KeyError, ValueError, TypeError, json.JSONDecodeError):
        return False
    package_root = Path(ASSET_ROOT, "pose_templates", "versions", version)
    try:
        from modal_service.templates import validate_template_package

        validate_template_package(package_root)
        return True
    except (OSError, ValueError, json.JSONDecodeError):
        return False


def _active_template_package():
    from modal_service.templates import TemplatePackageError, validate_template_package

    pointer = Path(ASSET_ROOT, "pose_templates", "active.json")
    if not pointer.is_file():
        raise TemplatePackageError("No active pose template package is installed.")
    version = str(json.loads(pointer.read_text(encoding="utf-8"))["version"])
    return validate_template_package(Path(ASSET_ROOT, "pose_templates", "versions", version))


def _result_payload(job: JobRecord) -> dict[str, object]:
    manifest = _asset_path(job.job_id, "poses", "manifest.json")
    if not manifest.is_file():
        raise DomainError("Mascot result metadata is unavailable.")
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    if payload.get("poseSetId") != job.pose_set_id or payload.get("masterId") != job.master_id:
        raise DomainError("Mascot result metadata is inconsistent.")
    poses = []
    for pose in payload.get("poses", []):
        item = dict(pose)
        pose_id = str(item.get("poseId", ""))
        if not pose_id.startswith("pose_"):
            raise DomainError("Mascot result contains an invalid pose reference.")
        item["downloadPath"] = f"/v1/mascot/jobs/{job.job_id}/poses/{pose_id}"
        poses.append(item)
    return payload | {"poses": poses}


def _decode_image(value: str) -> bytes:
    try:
        return base64.b64decode(value, validate=True)
    except ValueError as error:
        raise ImageValidationError("Image is not valid base64.") from error


def _serialize(job: JobRecord) -> dict[str, object]:
    payload = asdict(job) | {"state": job.state.value}
    for private_field in ("user_id", "idempotency_key", "source_key"):
        payload.pop(private_field, None)
    if job.state is JobState.AWAITING_MASTER_APPROVAL or job.master_id is not None:
        payload["masters"] = _master_references(job)
    return payload


def _master_references(job: JobRecord) -> list[dict[str, str]]:
    references: list[dict[str, str]] = []
    for index in range(1, 5):
        master_id = f"master_{index}"
        path = _asset_path(job.job_id, "masters", f"{master_id}.png")
        if path.is_file():
            references.append(
                {
                    "id": master_id,
                    "download_path": f"/v1/mascot/jobs/{job.job_id}/masters/{master_id}",
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
            )
    return references


def _deserialize(record: dict[str, object]) -> JobRecord:
    return JobRecord(**(record | {"state": JobState(record["state"])}))


def _get_job(job_id: str) -> JobRecord:
    try:
        return _deserialize(jobs[job_id])
    except KeyError as error:
        raise JobNotFound("Job was not found.") from error


def _ensure_owner(job: JobRecord, user_id: str) -> None:
    if job.user_id != user_id:
        raise JobNotFound("Job was not found.")


def _api_error(error: Exception):
    from fastapi import HTTPException

    code = getattr(error, "code", "INVALID_REQUEST")
    status = 429 if code in {"RATE_LIMITED", "COST_LIMIT_REACHED"} else 404 if code == "JOB_NOT_FOUND" else 400 if code in {"INVALID_IMAGE", "INVALID_REQUEST"} else 409
    detail: dict[str, object] = {"code": code, "message": str(error)}
    if code in {"RATE_LIMITED", "COST_LIMIT_REACHED"}:
        detail.update({"retry_at_utc": _next_utc_day(), "charge_incurred": False})
    return HTTPException(status_code=status, detail=detail)


def _next_utc_day() -> str:
    from datetime import UTC, datetime, timedelta

    tomorrow = datetime.now(UTC).date() + timedelta(days=1)
    return datetime.combine(tomorrow, datetime.min.time(), tzinfo=UTC).isoformat().replace("+00:00", "Z")


class GuardRejected(DomainError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _raise_guard_error(result: dict[str, object]) -> None:
    code = result.get("error_code")
    if code:
        raise GuardRejected(str(code), str(result.get("error_message", "Request was rejected.")))


def _request_context(user_id: str, idempotency_key: str) -> tuple[str, str]:
    normalized_user_id = user_id.strip()
    if not normalized_user_id:
        raise DomainError("Verified user identity and idempotency key are required.")
    return normalized_user_id, validate_idempotency_key(idempotency_key)


def utc_day_key() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).date().isoformat()


def _elapsed_ms(started: float) -> int:
    return max(0, int((time.monotonic() - started) * 1_000))


def _estimated_gpu_cost(gpu_elapsed_ms: int) -> float | None:
    raw_rate = os.getenv("MODAL_GPU_HOURLY_USD", "").strip()
    if not raw_rate:
        return None
    try:
        hourly_rate = float(raw_rate)
    except ValueError:
        return None
    return round(max(0.0, hourly_rate) * max(0, gpu_elapsed_ms) / 3_600_000, 6)


def _deliver_telemetry(path: Path) -> bool:
    import httpx

    url = os.getenv("SUPABASE_TELEMETRY_URL")
    key = os.getenv("SUPABASE_TELEMETRY_INGEST_KEY")
    payload, attempt = load(path)
    try:
        if not url or not key:
            raise RuntimeError("Telemetry delivery is not configured.")
        response = httpx.post(
            url,
            json=payload,
            headers={"X-GRU-Telemetry-Key": key},
            timeout=httpx.Timeout(2.0, connect=1.0),
        )
        response.raise_for_status()
        path.unlink(missing_ok=True)
        log_event("telemetry_delivery", outcome="accepted", event_name=payload.get("event_name"), delivery_attempt=attempt)
        return True
    except (httpx.HTTPError, RuntimeError, OSError) as error:
        record_failure(path, payload, attempt, type(error).__name__)
        log_event("telemetry_delivery", logging.WARNING, outcome="failed", error_class=type(error).__name__, delivery_attempt=attempt)
        return False


@app.function(
    image=api_image,
    secrets=[telemetry_secret],
    volumes={"/gru-telemetry": telemetry_volume},
    timeout=20,
    max_containers=2,
)
def emit_telemetry(event_id: str) -> None:
    """Deliver a previously persisted event; failure leaves it in the outbox."""
    telemetry_volume.reload()
    path = Path(TELEMETRY_ROOT, f"{event_id}.json")
    if path.is_file():
        _deliver_telemetry(path)
        telemetry_volume.commit()


@app.function(
    image=api_image,
    secrets=[telemetry_secret],
    volumes={"/gru-telemetry": telemetry_volume},
    schedule=modal.Cron("*/5 * * * *"),
    timeout=120,
    max_containers=1,
)
def flush_telemetry_outbox() -> dict[str, int]:
    telemetry_volume.reload()
    delivered = 0
    for path in due_files(Path(TELEMETRY_ROOT)):
        delivered += int(_deliver_telemetry(path))
    telemetry_volume.commit()
    pending = pending_count(Path(TELEMETRY_ROOT))
    operations["telemetry_outbox_pending"] = pending
    return {"delivered": delivered, "pending": pending}


def _track(
    job: JobRecord,
    event_name: str,
    stage: str,
    outcome: str,
    **kwargs: object,
) -> None:
    try:
        payload = enqueue(Path(TELEMETRY_ROOT), generation_event(job, event_name, stage, outcome, **kwargs))
        telemetry_volume.commit()
        emit_telemetry.spawn(str(payload["event_id"]))
    except Exception as error:  # Telemetry must never change a chargeable job outcome.
        log_event("telemetry_enqueue", logging.WARNING, outcome="failed", error_class=type(error).__name__)


def _endpoint_name(request) -> str:
    endpoint = request.scope.get("endpoint")
    name = getattr(endpoint, "__name__", None)
    return str(name or "unmatched")[:64]


@app.function(image=api_image, max_containers=1)
@modal.concurrent(max_inputs=1)
def enforce_rate_limit(scope: str, subject: str, limit: int) -> dict[str, object]:
    decision = consume_limit(usage, f"{scope}:{subject}", limit)
    return {
        "allowed": decision.allowed,
        "retry_after_seconds": decision.retry_after_seconds,
        "remaining": decision.remaining,
    }


@app.function(image=api_image, max_containers=1, volumes={"/gru-telemetry": telemetry_volume})
@modal.concurrent(max_inputs=1)
def register_job(
    user_id: str,
    idempotency_key: str,
    source_key: str,
    consent_policy_version: str,
    subject_identity: dict[str, object] | None = None,
) -> dict[str, object]:
    try:
        coordinator = JobCoordinator(jobs, idempotency, usage, LIMITS, utc_day_key())
        job, created = coordinator.register(
            user_id, idempotency_key, source_key, consent_policy_version, subject_identity
        )
        if created:
            _track(job, "job_registered", "api", "accepted")
        return {"job": _serialize(job), "created": created}
    except (DomainError, CostLimitExceeded, RateLimitExceeded) as error:
        return {"error_code": getattr(error, "code", "INVALID_REQUEST"), "error_message": str(error)}


@app.function(
    image=api_image,
    volumes={ASSET_ROOT: assets},
    schedule=modal.Cron("0 4 * * *"),
    timeout=60,
    max_containers=1,
)
def purge_expired_source_uploads() -> dict[str, int]:
    """Remove sensitive originals after the bounded retry window; never touches results."""
    originals = purge_expired_originals(Path(ASSET_ROOT))
    temporary = purge_expired_temporary_assets(Path(ASSET_ROOT))
    if originals or temporary:
        assets.commit()
    log_event("asset_retention_purge", originals_deleted=originals, temporary_deleted=temporary)
    return {"originals_deleted": originals, "temporary_deleted": temporary}


@app.function(
    image=api_image,
    volumes={"/gru-telemetry": telemetry_volume},
    schedule=modal.Cron("*/5 * * * *"),
    timeout=60,
    max_containers=1,
)
def recover_stale_generation_jobs() -> dict[str, int]:
    coordinator = JobCoordinator(jobs, idempotency, usage, LIMITS, utc_day_key())
    recovered = coordinator.recover_stale_workers()
    for job in recovered:
        _track(job, "worker_lease_expired", "scheduler", "failed", metadata={"error_code": "WORKER_LOST"})
    operations["stale_jobs_last_run"] = len(recovered)
    return {"recovered": len(recovered)}


@app.function(image=api_image, max_containers=1, volumes={ASSET_ROOT: assets, "/gru-telemetry": telemetry_volume})
@modal.concurrent(max_inputs=1)
def job_control(
    operation: str,
    job_id: str,
    user_id: str = "",
    master_id: str = "",
    call_id: str = "",
    outputs: list[bytes] | None = None,
    payload: dict[str, object] | None = None,
) -> dict[str, object]:
    try:
        coordinator = JobCoordinator(jobs, idempotency, usage, LIMITS, utc_day_key())
        command = JobOperation(operation)
        changed = False
        if command is JobOperation.AUTHORIZE_GENERATION:
            changed = coordinator.authorize_generation(job_id, user_id, GPU_GENERATION_ENABLED)
            job = coordinator.get(job_id)
            if changed:
                _track(
                    job,
                    "generation_reserved",
                    "scheduler",
                    "accepted",
                    reserved_cost_usd=LIMITS.estimated_generation_cost_usd,
                )
        elif command is JobOperation.START_MASTER:
            job, changed = coordinator.start_master_worker(job_id)
        elif command is JobOperation.RESUME_MASTER:
            job, changed = coordinator.resume_preempted_master(job_id, user_id)
        elif command is JobOperation.HEARTBEAT_WORKER:
            job, changed = coordinator.heartbeat_worker(job_id)
        elif command is JobOperation.COMMIT_MASTER:
            job, changed = coordinator.commit_master_outputs(
                job_id, lambda current: _persist_master_outputs(current, outputs or [])
            )
            if changed:
                _track(job, "master_candidates_persisted", "storage", "succeeded")
        elif command is JobOperation.FAIL_MASTER:
            job, changed = coordinator.transition_if_active(
                job_id, JobState.GENERATING_MASTER, JobState.FAILED, "MASTER_GENERATION_FAILED"
            )
            if changed:
                _track(job, "master_generation_failed", "worker", "failed")
        elif command is JobOperation.RECORD_GPU_CALL:
            job, changed = coordinator.record_gpu_call(job_id, call_id)
        elif command is JobOperation.APPROVE_MASTER:
            job, changed = coordinator.approve_master(job_id, user_id, master_id, POSE_PROMPT_VERSION)
            if changed:
                _track(job, "master_approved", "api", "accepted")
        elif command is JobOperation.VALIDATE_MASTER:
            job, changed = coordinator.validate_master(job_id)
            if changed:
                _track(job, "master_asset_validated", "validation", "succeeded")
        elif command is JobOperation.START_POSES:
            data = payload or {}
            job, changed = coordinator.start_pose_worker(
                job_id, user_id, dict(data.get("pose_choices") or {}),
                str(data.get("catalog_version") or ""), str(data.get("operation_id") or ""),
            )
            if changed:
                _track(job, "pose_generation_started", "scheduler", "accepted")
        elif command is JobOperation.COMMIT_POSES:
            job, changed = coordinator.commit_pose_outputs(
                job_id, lambda current: _persist_pose_outputs(current, outputs or [])
            )
            if changed:
                _track(job, "pose_generation_completed", "validation", "succeeded")
        elif command is JobOperation.FAIL_POSES:
            job, changed = coordinator.transition_if_active(
                job_id, JobState.GENERATING_POSES, JobState.FAILED, "POSE_GENERATION_FAILED"
            )
            if changed:
                _track(job, "pose_generation_failed", "worker", "failed")
        elif command is JobOperation.CANCEL:
            job, changed = coordinator.cancel(job_id, user_id)
            if changed:
                _track(job, "job_canceled", "api", "canceled")
        elif command is JobOperation.DELETE:
            try:
                job = coordinator.get(job_id)
                coordinator.ensure_owner(job, user_id)
            except JobNotFound:
                receipt = operations.get(f"deleted:{job_id}")
                if receipt == owner_counter_id(user_id):
                    return {"deleted": True, "idempotent_replay": True, "job_id": job_id}
                raise
            asset_groups_deleted = delete_job_assets(Path(ASSET_ROOT), job_id)
            assets.commit()
            deleted = coordinator.delete(job_id, user_id)
            operations[f"deleted:{job_id}"] = owner_counter_id(user_id)
            _track(
                deleted,
                "job_deletion_completed",
                "storage",
                "succeeded",
                metadata={"asset_groups_deleted": asset_groups_deleted},
            )
            return {"deleted": True, "idempotent_replay": False, "job_id": job_id}
        else:  # StrEnum exhaustiveness guard.
            raise DomainError("Unsupported job operation.")
        return {"job": _serialize(job), "changed": changed}
    except (DomainError, CostLimitExceeded, RateLimitExceeded) as error:
        return {"error_code": getattr(error, "code", "INVALID_REQUEST"), "error_message": str(error)}


def _schedule_master(job_id: str, user_id: str) -> dict[str, object]:
    authorization = job_control.remote(JobOperation.AUTHORIZE_GENERATION.value, job_id, user_id)
    _raise_guard_error(authorization)
    job_data = dict(authorization["job"])
    if str(job_data.get("state")) in {JobState.RECOVERY_REQUIRED.value, JobState.FAILED.value}:
        recovery = job_control.remote(JobOperation.RESUME_MASTER.value, job_id, user_id)
        _raise_guard_error(recovery)
        job_data = dict(recovery["job"])
    if not GPU_GENERATION_ENABLED or str(job_data.get("state")) != JobState.VALIDATING_INPUT.value:
        return job_data
    started = job_control.remote(JobOperation.START_MASTER.value, job_id)
    _raise_guard_error(started)
    job_data = dict(started["job"])
    if not bool(started["changed"]):
        return job_data
    function_call = generate_master.spawn(job_id)
    recorded = job_control.remote(JobOperation.RECORD_GPU_CALL.value, job_id, call_id=function_call.object_id)
    _raise_guard_error(recorded)
    return dict(recorded["job"])


def _schedule_web_master(job_id: str, user_id: str) -> dict[str, object]:
    """Translate expected scheduler guards into safe V2 API responses."""
    try:
        return _schedule_master(job_id, user_id)
    except GuardRejected as error:
        return {"error_code": error.code, "error_message": str(error)}


def _schedule_web_poses(
    job_id: str,
    user_id: str,
    pose_choices: dict[str, str],
    catalog_version: str,
    operation_id: str,
) -> dict[str, object]:
    """Start one idempotent pose worker only after all capability guards pass."""
    from modal_service.catalog import POSE_CATALOG_VERSION, validate_pose_choices

    try:
        if not GPU_GENERATION_ENABLED:
            raise GuardRejected("GENERATION_DISABLED", "GPU generation is disabled.")
        if catalog_version != POSE_CATALOG_VERSION or not _templates_installed():
            raise GuardRejected("POSE_CAPABILITY_MISMATCH", "The approved pose package is unavailable.")
        validate_pose_choices(pose_choices)
        started = job_control.remote(
            JobOperation.START_POSES.value, job_id, user_id,
            payload={"pose_choices": pose_choices, "catalog_version": catalog_version, "operation_id": operation_id},
        )
        _raise_guard_error(started)
        if not bool(started["changed"]):
            return dict(started["job"])
        call = generate_poses_v2.spawn(job_id)
        recorded = job_control.remote(JobOperation.RECORD_GPU_CALL.value, job_id, call_id=call.object_id)
        _raise_guard_error(recorded)
        return dict(recorded["job"])
    except (GuardRejected, ValueError) as error:
        return {"error_code": getattr(error, "code", "POSE_CHOICES_INVALID"), "error_message": str(error)}


@app.function(
    image=gpu_image,
    gpu=MASTER_GPU,
    timeout=LIMITS.model_timeout_seconds,
    min_containers=0,
    max_containers=LIMITS.max_containers,
    scaledown_window=30,
    # Telemetry is persisted before delivery and therefore survives Supabase outages.
    volumes={ASSET_ROOT: assets, MODEL_ROOT: models, "/gru-telemetry": telemetry_volume},
)
def generate_master(job_id: str) -> None:
    """GPU boundary. The Qwen provider is enabled only after a smoke fixture exists."""
    if not GPU_GENERATION_ENABLED:
        logging.warning("generation_blocked job_id=%s", job_id)
        return
    started = job_control.remote(JobOperation.START_MASTER.value, job_id)
    _raise_guard_error(started)
    job = _get_job(job_id)
    if not bool(started["changed"]) and job.state is not JobState.GENERATING_MASTER:
        return
    worker_started = time.monotonic()
    _track(job, "master_worker_started", "worker", "accepted")
    try:
        outputs, generation_metadata = _generate_qwen_masters(job)
        committed = job_control.remote(JobOperation.COMMIT_MASTER.value, job_id, outputs=outputs)
        _raise_guard_error(committed)
        worker_ms = _elapsed_ms(worker_started)
        _track(
            job,
            "master_worker_completed",
            "worker",
            "succeeded",
            duration_ms=worker_ms,
            gpu_elapsed_ms=worker_ms,
            reserved_cost_usd=LIMITS.estimated_generation_cost_usd,
            estimated_cost_usd=_estimated_gpu_cost(worker_ms),
            metadata=generation_metadata,
        )
    except Exception as error:  # GPU libraries expose unstable exception classes.
        logging.exception("master_generation_failed job_id=%s", job.job_id)
        failed = job_control.remote(JobOperation.FAIL_MASTER.value, job_id)
        _raise_guard_error(failed)
        worker_ms = _elapsed_ms(worker_started)
        _track(
            job,
            "master_worker_failed",
            "worker",
            "failed",
            duration_ms=worker_ms,
            gpu_elapsed_ms=worker_ms,
            reserved_cost_usd=LIMITS.estimated_generation_cost_usd,
            estimated_cost_usd=_estimated_gpu_cost(worker_ms),
            metadata={"error_class": type(error).__name__},
        )
        if bool(failed["changed"]):
            raise error


@app.function(
    image=gpu_image,
    gpu=MASTER_GPU,
    timeout=LIMITS.model_timeout_seconds,
    min_containers=0,
    max_containers=LIMITS.max_containers,
    scaledown_window=30,
    volumes={ASSET_ROOT: assets, MODEL_ROOT: models, "/gru-telemetry": telemetry_volume},
)
def generate_poses_v2(job_id: str) -> None:
    """Generate exactly the three chosen roles from the approved Master."""
    if not GPU_GENERATION_ENABLED:
        return
    job = _get_job(job_id)
    if job.state is not JobState.GENERATING_POSES:
        return
    started = time.monotonic()
    try:
        outputs, metadata = _generate_qwen_poses(job)
        committed = job_control.remote(JobOperation.COMMIT_POSES.value, job_id, outputs=outputs)
        _raise_guard_error(committed)
        elapsed = _elapsed_ms(started)
        _track(job, "pose_worker_completed", "worker", "succeeded", duration_ms=elapsed,
               gpu_elapsed_ms=elapsed, estimated_cost_usd=_estimated_gpu_cost(elapsed), metadata=metadata)
    except Exception as error:
        logging.exception("pose_generation_failed job_id=%s", job_id)
        failed = job_control.remote(JobOperation.FAIL_POSES.value, job_id)
        _raise_guard_error(failed)
        if bool(failed["changed"]):
            raise error


def _generate_qwen_poses(job: JobRecord) -> tuple[list[bytes], dict[str, object]]:
    from io import BytesIO
    import torch
    from PIL import Image
    from modal_service.catalog import build_pose_prompt, validate_pose_choices
    from modal_service.image_processing import AssetQualityError
    from modal_service.segmentation import segment_mascot

    if not job.master_id:
        raise DomainError("An approved Master is required.")
    package = _active_template_package()
    by_option = {str(item["option_id"]): item for item in package.manifest["poses"]}
    selected = validate_pose_choices(job.pose_choices)
    master = Image.open(_asset_path(job.job_id, "masters", f"{job.master_id}.png")).convert("RGBA")
    generator, segmenter, model_load_ms = _load_generation_stack()
    outputs: list[bytes] = []
    retries = 0
    inference_ms = 0
    for index, pose in enumerate(selected):
        item = by_option[pose.option_id]
        reference = Image.open(package.root / str(item["reference"])).convert("RGB")
        accepted: bytes | None = None
        for attempt in range(2):
            inference_started = time.monotonic()
            generated = generator(
                image=[master.convert("RGB"), reference],
                prompt=build_pose_prompt(job.subject_identity, pose.instruction),
                negative_prompt="background, ground shadow, checkerboard, frame, text, watermark, invented marks",
                true_cfg_scale=1.0,
                generator=torch.Generator("cuda").manual_seed(10_000 + index * 100 + attempt),
                num_inference_steps=4,
            ).images[0]
            inference_ms += _elapsed_ms(inference_started)
            buffer = BytesIO(); generated.save(buffer, format="PNG")
            try:
                accepted, _ = segment_mascot(buffer.getvalue(), lambda: segmenter)
                break
            except AssetQualityError:
                retries += 1
        if accepted is None:
            raise RuntimeError(f"POSE_ASSET_QC_FAILED:{pose.role}")
        outputs.append(accepted)
    return outputs, {"pose_count": 3, "isolated_retries": retries, "model_load_ms": model_load_ms, "inference_ms": inference_ms}


def _generate_qwen_masters(job: JobRecord) -> tuple[list[bytes], dict[str, object]]:
    """Generate three QC-passing Masters, with at most two technical substitutes."""
    from io import BytesIO
    import torch
    from PIL import Image

    from modal_service.catalog import build_master_prompt
    from modal_service.image_processing import AssetQualityError
    from modal_service.segmentation import segment_mascot

    job_control.remote(JobOperation.HEARTBEAT_WORKER.value, job.job_id)
    source = Image.open(_asset_path(job.job_id, "original", "source.bin")).convert("RGB")
    source.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
    pipeline, segmenter, model_load_ms = _load_generation_stack()
    logging.info("event=model_loaded model=qwen-image-edit-2511-lightning duration_ms=%d", model_load_ms)
    outputs: list[bytes] = []
    inference_ms = 0
    rejected: list[list[str]] = []
    for seed in range(5):
        if len(outputs) == 3:
            break
        job_control.remote(JobOperation.HEARTBEAT_WORKER.value, job.job_id)
        inference_started = time.monotonic()
        generated = pipeline(
            image=[source],
            prompt=build_master_prompt(job.subject_identity),
            negative_prompt="background, ground shadow, checkerboard, frame, text, watermark, extra subject, invented marks",
            true_cfg_scale=1.0,
            generator=torch.Generator("cuda").manual_seed(seed),
            num_inference_steps=4,
        ).images[0]
        buffer = BytesIO()
        generated.save(buffer, format="PNG")
        try:
            normalized, check = segment_mascot(buffer.getvalue(), lambda: segmenter)
            outputs.append(normalized)
            logging.info("event=master_qc_passed candidate=%d alpha_ratio=%s", seed + 1, check.alpha_ratio)
        except AssetQualityError as error:
            rejected.append(list(error.check.safe_reasons))
            logging.warning("event=master_qc_failed candidate=%d reasons=%s", seed + 1, error.check.safe_reasons)
        elapsed = _elapsed_ms(inference_started)
        inference_ms += elapsed
        logging.info("event=master_generated index=%d duration_ms=%d", seed + 1, elapsed)
    if len(outputs) != 3:
        raise RuntimeError("MASTER_ASSET_QC_FAILED")
    return outputs, {
        "candidate_count": len(outputs), "replacement_candidates": len(rejected),
        "rejected_reasons": rejected, "model_load_ms": model_load_ms, "inference_ms": inference_ms,
    }


def _load_generation_stack():
    """Load pinned Qwen edit and SAM 2.1 models once per warm worker."""
    import math
    import torch
    from diffusers import FlowMatchEulerDiscreteScheduler, QwenImageEditPlusPipeline
    from diffusers.models import QwenImageTransformer2DModel
    from huggingface_hub import hf_hub_download
    from transformers import pipeline as transformers_pipeline
    from modal_service.segmentation import SAM_MODEL_ID, SAM_MODEL_REVISION

    started = time.monotonic()
    transformer = QwenImageTransformer2DModel.from_pretrained(
        QWEN_MODEL_ID, subfolder="transformer", revision=QWEN_MODEL_REVISION,
        torch_dtype=torch.bfloat16, cache_dir=MODEL_ROOT,
    )
    scheduler = FlowMatchEulerDiscreteScheduler.from_config({
        "base_image_seq_len": 256, "base_shift": math.log(3), "invert_sigmas": False,
        "max_image_seq_len": 8192, "max_shift": math.log(3), "num_train_timesteps": 1000,
        "shift": 1.0, "shift_terminal": None, "stochastic_sampling": False,
        "time_shift_type": "exponential", "use_beta_sigmas": False,
        "use_dynamic_shifting": True, "use_exponential_sigmas": False, "use_karras_sigmas": False,
    })
    generator = QwenImageEditPlusPipeline.from_pretrained(
        QWEN_MODEL_ID, transformer=transformer, scheduler=scheduler, revision=QWEN_MODEL_REVISION,
        torch_dtype=torch.bfloat16, cache_dir=MODEL_ROOT,
    )
    lora_path = hf_hub_download(
        LIGHTNING_MODEL_ID, LIGHTNING_WEIGHT, revision=LIGHTNING_MODEL_REVISION, cache_dir=MODEL_ROOT,
    )
    generator.load_lora_weights(lora_path)
    generator = generator.to("cuda")
    segmenter = transformers_pipeline(
        task="mask-generation", model=SAM_MODEL_ID, revision=SAM_MODEL_REVISION, device=0,
    )
    models.commit()
    return generator, segmenter, _elapsed_ms(started)


def _master_prompt(subject_identity: dict[str, object] | None = None) -> str:
    from modal_service.catalog import build_master_prompt

    return build_master_prompt(subject_identity)


def _persist_master_outputs(job: JobRecord, outputs: list[bytes]) -> None:
    from modal_service.image_processing import inspect_asset

    if not outputs:
        raise DomainError("Master generation returned no images.")
    staging = Path(ASSET_ROOT, "temporary", job.job_id, "masters")
    target = Path(ASSET_ROOT, "masters", job.job_id)
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True, exist_ok=True)
    checks: list[dict[str, object]] = []
    for index, content in enumerate(outputs, start=1):
        check = inspect_asset(content)
        if check.status != "passed":
            raise DomainError("MASTER_ASSET_QC_FAILED")
        destination = staging / f"master_{index}.png"
        destination.write_bytes(content)
        checks.append({"assetType": "master", "assetId": f"master_{index}", **check.as_dict()})
    (staging / "checks.json").write_text(json.dumps({"checks": checks}, separators=(",", ":")), encoding="utf-8")
    shutil.rmtree(target, ignore_errors=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    staging.replace(target)
    assets.commit()


def _persist_pose_outputs(job: JobRecord, outputs: list[bytes]) -> None:
    from modal_service.catalog import MASTER_PROMPT_VERSION, POSE_PROMPT_VERSION, validate_pose_choices
    from modal_service.image_processing import inspect_asset

    selected = validate_pose_choices(job.pose_choices)
    if len(outputs) != len(selected) or not job.master_id:
        raise DomainError("Pose generation returned an incomplete set.")
    package = _active_template_package()
    by_option = {str(item["option_id"]): item for item in package.manifest["poses"]}
    staging = Path(ASSET_ROOT, "temporary", job.job_id, "poses")
    target = Path(ASSET_ROOT, "poses", job.job_id)
    shutil.rmtree(staging, ignore_errors=True); staging.mkdir(parents=True, exist_ok=True)
    manifest_poses: list[dict[str, object]] = []
    checks: list[dict[str, object]] = []
    for definition, content in zip(selected, outputs, strict=True):
        check = inspect_asset(content)
        if check.status != "passed":
            raise DomainError(f"POSE_ASSET_QC_FAILED:{definition.role}")
        filename = f"{definition.role}.png"
        (staging / filename).write_bytes(content)
        template = by_option[definition.option_id]
        manifest_poses.append({
            "poseId": definition.option_id, "role": definition.role, "optionId": definition.option_id,
            "templateId": definition.template_id, "templateVersion": package.version,
            "templateSha256": template["sha256"], "fileName": filename,
            "size": len(content), "sha256": hashlib.sha256(content).hexdigest(),
        })
        checks.append({"assetType": "pose", "assetId": definition.role, **check.as_dict()})
    digest = hashlib.sha256("".join(str(item["sha256"]) for item in manifest_poses).encode()).hexdigest()[:24]
    job.pose_set_id = f"set_{digest}"
    manifest = {
        "poseSetId": job.pose_set_id, "masterId": job.master_id, "catalogVersion": job.catalog_version,
        "templateVersion": package.version, "modelVersion": job.model_version,
        "masterPromptVersion": MASTER_PROMPT_VERSION, "poseWorkerVersion": POSE_PROMPT_VERSION,
        "poses": manifest_poses,
    }
    (staging / "manifest.json").write_text(json.dumps(manifest, separators=(",", ":")), encoding="utf-8")
    (staging / "checks.json").write_text(json.dumps({"checks": checks}, separators=(",", ":")), encoding="utf-8")
    shutil.rmtree(target, ignore_errors=True); target.parent.mkdir(parents=True, exist_ok=True); staging.replace(target)
    assets.commit()


@app.function(image=api_image, volumes={ASSET_ROOT: assets}, max_containers=1)
def normalize_master_assets(job_id: str) -> dict[str, object]:
    """Administrative CPU-only migration for Masters created before alpha cleanup."""
    from modal_service.image_processing import remove_connected_flat_background, transparency_ratio

    if not job_id.startswith("job_") or not job_id[4:].isalnum() or len(job_id) > 96:
        raise ValueError("Invalid job identifier.")
    target = Path(ASSET_ROOT, "masters", job_id)
    updated: list[dict[str, object]] = []
    for path in sorted(target.glob("master_[1-4].png")):
        normalized = remove_connected_flat_background(path.read_bytes())
        path.write_bytes(normalized)
        updated.append({"master_id": path.stem, "transparency_ratio": round(transparency_ratio(normalized), 4)})
    if not updated:
        raise ValueError("No Master assets found.")
    assets.commit()
    return {"job_id": job_id, "masters": updated}


@app.function(
    image=api_image,
    volumes={ASSET_ROOT: assets, "/gru-telemetry": telemetry_volume},
    secrets=[firebase_admin_secret, web_bff_jwt_secret],
    max_containers=1,
)
@modal.asgi_app()
def api():
    from fastapi import Depends, FastAPI, Header, Request
    from fastapi.exceptions import RequestValidationError
    from fastapi.responses import JSONResponse
    import firebase_admin
    from firebase_admin import app_check as firebase_app_check
    from firebase_admin import credentials
    from google.auth.transport.requests import Request as GoogleRequest
    from google.oauth2 import id_token

    service = FastAPI(title="GRU Mascot API", docs_url=None, redoc_url=None)
    credentials_json = os.environ.get("FIREBASE_ADMIN_CREDENTIALS_JSON")
    if not credentials_json:
        raise RuntimeError("Firebase Admin credentials are required for protected API startup.")
    try:
        firebase_admin.get_app()
    except ValueError:
        firebase_admin.initialize_app(credentials.Certificate(json.loads(credentials_json)))

    @service.middleware("http")
    async def request_observability(request, call_next):
        request_id = secrets.token_hex(6)
        request.state.request_id = request_id
        started = time.monotonic()
        content_length = request.headers.get("content-length")
        if content_length and content_length.isdigit() and int(content_length) > MAX_REQUEST_BODY_BYTES:
            return JSONResponse(
                status_code=413,
                content={"detail": {"code": "REQUEST_TOO_LARGE", "message": "The request body is too large."}},
                headers={"X-Request-ID": request_id},
            )
        try:
            response = await call_next(request)
        except Exception as error:
            log_event("http_request", logging.ERROR, request_id=request_id, method=request.method,
                      endpoint=_endpoint_name(request), outcome="failure", error_class=type(error).__name__,
                      duration_ms=_elapsed_ms(started))
            raise
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        log_event("http_request", request_id=request_id, method=request.method, endpoint=_endpoint_name(request),
                  status=response.status_code, duration_ms=_elapsed_ms(started), content_length=content_length or "unknown")
        return response

    @service.exception_handler(RequestValidationError)
    async def request_validation_error(_request, error: RequestValidationError):
        failures = ",".join(
            f"{'.'.join(str(item) for item in issue.get('loc', ()))}:{issue.get('type', 'invalid')}"
            for issue in error.errors()[:5]
        )
        log_event("request_validation", outcome="rejected", failures=failures[:300])
        return JSONResponse(
            status_code=422,
            content={"detail": {"code": "INVALID_REQUEST", "message": "The request format is invalid."}},
        )

    # These dependencies live inside the ASGI factory. Keep FastAPI markers in
    # defaults so postponed annotations cannot turn them into public query args.
    async def verified_user(authorization: str | None = Header(default=None)) -> str:
        import asyncio
        from fastapi import HTTPException

        global_limit = await asyncio.to_thread(
            enforce_rate_limit.remote, "protected", "global", LIMITS.global_requests_per_minute
        )
        if not bool(global_limit["allowed"]):
            raise HTTPException(
                status_code=429,
                detail={"code": "RATE_LIMITED", "message": "Too many requests. Try again shortly."},
                headers={"Retry-After": str(global_limit["retry_after_seconds"])},
            )
        try:
            token = bearer_token(authorization)
        except AuthenticationRejected as error:
            from fastapi import HTTPException
            raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": str(error)}) from error
        try:
            claims = id_token.verify_firebase_token(token, GoogleRequest(), audience="gru-mascote")
            if not valid_firebase_claims(claims, FIREBASE_PROJECT_ID):
                raise ValueError("Unexpected Firebase token claims.")
            return str(claims.get("uid") or claims["sub"])
        except Exception as error:
            log_event("firebase_token_rejected", outcome="rejected", error_class=type(error).__name__)
            from fastapi import HTTPException
            raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "A valid identity is required."}) from error

    async def verified_app_check(x_firebase_appcheck: str | None = Header(default=None)) -> None:
        try:
            token = app_check_token(x_firebase_appcheck)
        except AuthenticationRejected as error:
            from fastapi import HTTPException
            raise HTTPException(status_code=401, detail={"code": "APP_CHECK_REQUIRED", "message": str(error)}) from error
        try:
            firebase_app_check.verify_token(token)
        except Exception as error:
            log_event("firebase_app_check_rejected", outcome="rejected", error_class=type(error).__name__)
            from fastapi import HTTPException
            raise HTTPException(status_code=401, detail={"code": "APP_CHECK_REQUIRED", "message": "A valid app proof is required."}) from error

    async def cost_context(
        request: Request,
        user_id: str = Depends(verified_user),
        _: None = Depends(verified_app_check),
        x_idempotency_key: str | None = Header(default=None),
    ) -> tuple[str, str]:
        import asyncio
        from fastapi import HTTPException

        decision = await asyncio.to_thread(
            enforce_rate_limit.remote, "write", owner_counter_id(user_id), LIMITS.writes_per_user_per_minute
        )
        if not bool(decision["allowed"]):
            raise HTTPException(
                status_code=429,
                detail={"code": "RATE_LIMITED", "message": "Too many write requests. Try again shortly."},
                headers={"Retry-After": str(decision["retry_after_seconds"])},
            )
        return _request_context(user_id, x_idempotency_key or "")

    async def secure_user(
        request: Request,
        user_id: str = Depends(verified_user),
        _: None = Depends(verified_app_check),
    ) -> str:
        import asyncio
        from fastapi import HTTPException

        decision = await asyncio.to_thread(
            enforce_rate_limit.remote, "read", owner_counter_id(user_id), LIMITS.reads_per_user_per_minute
        )
        if not bool(decision["allowed"]):
            raise HTTPException(
                status_code=429,
                detail={"code": "RATE_LIMITED", "message": "Too many read requests. Try again shortly."},
                headers={"Retry-After": str(decision["retry_after_seconds"])},
            )
        return user_id

    @service.get("/health")
    async def health() -> dict[str, object]:
        """Compatibility endpoint; use the explicit probes for automation."""
        return generation_payload(
            service=APP_NAME,
            environment=ENVIRONMENT.value,
            generation_enabled=GPU_GENERATION_ENABLED,
            templates_installed=_templates_installed(),
            model_configured=_model_configuration_present(),
        )

    @service.get("/health/live")
    async def health_live() -> dict[str, object]:
        return live_payload(APP_NAME, ENVIRONMENT.value)

    @service.get("/health/ready")
    async def health_ready():
        from fastapi.responses import JSONResponse

        dependency_checks: dict[str, object] = {
            "firebase_credentials": "healthy" if bool(credentials_json) else "unhealthy",
            "asset_volume": "healthy" if Path(ASSET_ROOT).is_dir() else "unhealthy",
            "telemetry_volume": "healthy" if Path(TELEMETRY_ROOT).parent.is_dir() else "unhealthy",
        }
        try:
            jobs.get("__health_probe__")
            dependency_checks["job_store"] = "healthy"
        except Exception:
            dependency_checks["job_store"] = "unhealthy"
        dependency_checks["telemetry_outbox_pending"] = int(operations.get("telemetry_outbox_pending", 0))
        dependency_checks["stale_jobs_last_run"] = int(operations.get("stale_jobs_last_run", 0))
        payload = ready_payload(
            service=APP_NAME,
            environment=ENVIRONMENT.value,
            model_configured=_model_configuration_present(),
            dependency_checks=dependency_checks,
        )
        return JSONResponse(status_code=200 if payload["status"] == "ready" else 503, content=payload)

    @service.get("/health/generation")
    async def health_generation():
        from fastapi.responses import JSONResponse

        payload = generation_payload(
            service=APP_NAME,
            environment=ENVIRONMENT.value,
            generation_enabled=GPU_GENERATION_ENABLED,
            templates_installed=_templates_installed(),
            model_configured=_model_configuration_present(),
        )
        return JSONResponse(status_code=200 if payload["status"] == "ready" else 503, content=payload)

    def _model_configuration_present() -> bool:
        return bool(QWEN_MODEL_ID and QWEN_MODEL_REVISION and LIGHTNING_MODEL_ID and LIGHTNING_MODEL_REVISION and LIGHTNING_WEIGHT)

    def _web_capabilities() -> dict[str, object]:
        from modal_service.capabilities import capability_payload

        return capability_payload(
            generation_enabled=GPU_GENERATION_ENABLED,
            model_configured=_model_configuration_present(),
            templates_installed=_templates_installed(),
            pose_worker_installed=True,
        )

    @service.get("/health/legacy")
    async def health_legacy() -> dict[str, object]:
        """Temporary legacy shape for existing Android diagnostic builds."""
        return {
            "service": APP_NAME,
            "environment": ENVIRONMENT.value,
            "generation_enabled": GPU_GENERATION_ENABLED,
            "templates_installed": _templates_installed(),
            "model_configured": _model_configuration_present(),
        }

    # V2 is isolated in its own module. V1 below remains the Android
    # Firebase/App Check contract and is intentionally not modified.
    from modal_service.web_v2 import WebV2Dependencies, install_web_v2_routes
    from modal_service.image_processing import strip_image_metadata

    def _approve_web_master(job_id: str, user_id: str, master_id: str) -> dict[str, object]:
        approved = job_control.remote(JobOperation.APPROVE_MASTER.value, job_id, user_id, master_id=master_id)
        _raise_guard_error(approved)
        validated = job_control.remote(JobOperation.VALIDATE_MASTER.value, job_id, user_id)
        _raise_guard_error(validated)
        return validated

    install_web_v2_routes(
        service,
        WebV2Dependencies(
            get_job=_get_job,
            ensure_owner=_ensure_owner,
            api_error=_api_error,
            asset_path=_asset_path,
            decode_image=_decode_image,
            validate_image=validate_image,
            strip_metadata=strip_image_metadata,
            register_job=register_job.remote,
            schedule_master=_schedule_web_master,
            approve_master=_approve_web_master,
            schedule_poses=_schedule_web_poses,
            capabilities=_web_capabilities,
            templates_installed=_templates_installed,
            generation_enabled=GPU_GENERATION_ENABLED,
            max_body_bytes=MAX_REQUEST_BODY_BYTES,
            assets=assets,
            operations=operations,
            environment=ENVIRONMENT.value,
            app_name=APP_NAME,
        ),
        os.getenv("MODAL_BFF_JWT_SECRET"),
    )

    @service.post("/v1/mascot/jobs", status_code=202)
    async def create_job(request: CreateJobRequest, context: tuple[str, str] = Depends(cost_context)):
        user_id, key = context
        try:
            if request.consent_policy_version != CONSENT_POLICY_VERSION:
                raise GuardRejected("CONSENT_REQUIRED", "Current image-processing consent is required.")
            content = _decode_image(request.image_base64)
            _, _, _ = validate_image(content, request.content_type)
            from modal_service.image_processing import strip_image_metadata
            content = strip_image_metadata(content)
            _, _, _ = validate_image(content)
            digest = hashlib.sha256(content).hexdigest()
            registration = register_job.remote(user_id, key, f"original/{digest}", request.consent_policy_version)
            _raise_guard_error(registration)
            job_data = dict(registration["job"])
            destination = _asset_path(str(job_data["job_id"]), "original", "source.bin")
            if not destination.is_file() or hashlib.sha256(destination.read_bytes()).hexdigest() != digest:
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(content)
                assets.commit()
            job_data = _schedule_master(str(job_data["job_id"]), user_id)
            return job_data | {"idempotent_replay": not bool(registration["created"])}
        except (ImageValidationError, DomainError, CostLimitExceeded, RateLimitExceeded) as error:
            raise _api_error(error) from error

    @service.get("/v1/mascot/jobs/{job_id}")
    async def read_job(job_id: str, user_id: str = Depends(secure_user)):
        try:
            job = _get_job(job_id)
            _ensure_owner(job, user_id)
            return _serialize(job)
        except DomainError as error:
            raise _api_error(error) from error

    @service.get("/v1/mascot/idempotency/{idempotency_key}")
    async def recover_job(idempotency_key: str, user_id: str = Depends(secure_user)):
        try:
            idempotency_key = validate_idempotency_key(idempotency_key)
            job_id = str(idempotency[_record_key(user_id, idempotency_key)])
            job = _get_job(job_id)
            _ensure_owner(job, user_id)
            return _serialize(job)
        except KeyError as error:
            raise _api_error(JobNotFound("Job was not found.")) from error
        except DomainError as error:
            raise _api_error(error) from error

    @service.post("/v1/mascot/jobs/{job_id}/generate-master", status_code=202)
    async def start_master_generation(job_id: str, context: tuple[str, str] = Depends(cost_context)):
        try:
            job = _get_job(job_id)
            _ensure_owner(job, context[0])
            if not GPU_GENERATION_ENABLED:
                raise GuardRejected("GENERATION_DISABLED", "GPU generation is disabled.")
            operation_key = _operation_key(context[0], f"generate-master:{job_id}")
            if operation_key in idempotency:
                return _serialize(_get_job(job_id))
            job_data = _schedule_master(job_id, context[0])
            idempotency[operation_key] = job_id
            return job_data
        except (DomainError, CostLimitExceeded, RateLimitExceeded) as error:
            raise _api_error(error) from error

    @service.post("/v1/mascot/jobs/{job_id}/approve-master", status_code=202)
    async def approve_master(
        job_id: str,
        request: ApproveMasterRequest,
        context: tuple[str, str] = Depends(cost_context),
    ):
        try:
            job = _get_job(job_id)
            _ensure_owner(job, context[0])
            operation_key = _operation_key(context[0], f"approve:{job_id}:{request.master_id}")
            if operation_key in idempotency:
                return _serialize(job)
            if not _asset_path(job_id, "masters", f"{request.master_id}.png").is_file():
                raise JobNotFound("Master was not found.")
            approval = job_control.remote(
                JobOperation.APPROVE_MASTER.value, job_id, context[0], master_id=request.master_id
            )
            _raise_guard_error(approval)
            idempotency[operation_key] = job.job_id
            return dict(approval["job"])
        except DomainError as error:
            raise _api_error(error) from error

    @service.post("/v1/mascot/jobs/{job_id}/cancel")
    async def cancel_job(job_id: str, context: tuple[str, str] = Depends(cost_context)):
        try:
            job = _get_job(job_id)
            _ensure_owner(job, context[0])
            operation_key = _operation_key(context[0], f"cancel:{job_id}")
            if operation_key in idempotency:
                return _serialize(job)
            canceled = job_control.remote(JobOperation.CANCEL.value, job_id, context[0])
            _raise_guard_error(canceled)
            current = _deserialize(dict(canceled["job"]))
            if current.gpu_call_id:
                modal.FunctionCall.from_id(current.gpu_call_id).cancel()
            idempotency[operation_key] = job.job_id
            return dict(canceled["job"])
        except DomainError as error:
            raise _api_error(error) from error

    @service.delete("/v1/mascot/jobs/{job_id}", status_code=202)
    async def delete_job(job_id: str, context: tuple[str, str] = Depends(cost_context)):
        try:
            deleted = job_control.remote(JobOperation.DELETE.value, job_id, context[0])
            _raise_guard_error(deleted)
            return deleted
        except DomainError as error:
            raise _api_error(error) from error

    @service.get("/v1/mascot/jobs/{job_id}/result")
    async def result(job_id: str, user_id: str = Depends(secure_user)):
        try:
            job = _get_job(job_id)
            _ensure_owner(job, user_id)
            if job.state is not JobState.COMPLETED:
                raise DomainError("Mascot result is not ready.")
            return _result_payload(job)
        except DomainError as error:
            raise _api_error(error) from error

    @service.get("/v1/mascot/jobs/{job_id}/masters/{master_id}")
    async def download_master(job_id: str, master_id: str, user_id: str = Depends(secure_user)):
        from fastapi.responses import FileResponse
        if master_id not in {"master_1", "master_2", "master_3", "master_4"}:
            raise _api_error(JobNotFound("Master was not found."))
        job = _get_job(job_id)
        _ensure_owner(job, user_id)
        path = _asset_path(job_id, "masters", f"{master_id}.png")
        if not path.is_file():
            raise _api_error(JobNotFound("Master was not found."))
        return FileResponse(path, media_type="image/png", filename=f"{master_id}.png")

    @service.get("/v1/mascot/jobs/{job_id}/poses/{pose_id}")
    async def download_pose(job_id: str, pose_id: str, user_id: str = Depends(secure_user)):
        from fastapi.responses import FileResponse
        try:
            job = _get_job(job_id)
            _ensure_owner(job, user_id)
            if job.state is not JobState.COMPLETED:
                raise JobNotFound("Pose was not found.")
            result_payload = _result_payload(job)
            pose = next((item for item in result_payload["poses"] if item.get("poseId") == pose_id), None)
            if pose is None:
                raise JobNotFound("Pose was not found.")
            filename = Path(str(pose.get("fileName", ""))).name
            if not filename:
                raise JobNotFound("Pose was not found.")
            path = _asset_path(job_id, "poses", filename)
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != pose.get("sha256"):
                raise JobNotFound("Pose was not found.")
            return FileResponse(path, media_type="image/png", filename=f"{pose_id}.png")
        except DomainError as error:
            raise _api_error(error) from error

    @service.post("/v1/mascot/jobs/{job_id}/consistency", status_code=202)
    async def run_consistency(job_id: str, context: tuple[str, str] = Depends(cost_context)):
        return _template_assets_required(job_id, context[0])

    @service.post("/v1/mascot/jobs/{job_id}/generate-poses", status_code=202)
    async def generate_poses(job_id: str, context: tuple[str, str] = Depends(cost_context)):
        return _template_assets_required(job_id, context[0])

    @service.post("/v1/mascot/jobs/{job_id}/retry-pose", status_code=202)
    async def retry_pose(
        job_id: str,
        request: PoseRequest,
        context: tuple[str, str] = Depends(cost_context),
    ):
        del request
        return _template_assets_required(job_id, context[0])

    def _template_assets_required(job_id: str, user_id: str):
        from fastapi import HTTPException
        try:
            job = _get_job(job_id)
            _ensure_owner(job, user_id)
        except DomainError as error:
            raise _api_error(error) from error
        if not _templates_installed():
            raise HTTPException(
                status_code=409,
                detail={"code": "TEMPLATE_ASSETS_UNAVAILABLE", "message": "Official pose templates are not installed."},
            )
        if not GPU_GENERATION_ENABLED:
            raise HTTPException(
                status_code=409,
                detail={"code": "GENERATION_DISABLED", "message": "GPU generation is disabled."},
            )
        raise HTTPException(
            status_code=501,
            detail={"code": "GENERATION_PIPELINE_NOT_READY", "message": "Pose generation awaits approved evaluation tooling."},
        )

    return service

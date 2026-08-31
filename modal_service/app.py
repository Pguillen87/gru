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
from contextvars import ContextVar
from dataclasses import asdict, fields
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal
import modal
from pydantic import BaseModel, Field

from modal_service.catalog import (
    DEFAULT_POSE_CHOICES,
    MASTER_PROMPT,
    MASTER_PROMPT_VERSION,
    POSE_PROMPT,
    POSE_PROMPT_VERSION,
    POSE_TEMPLATE_VERSION,
    POSE_OPTIONS,
    build_master_negative_prompt,
    build_pose_negative_prompt,
    build_master_prompt,
    build_pose_prompt,
    pose_option,
    validate_pose_choices,
)
from modal_service.bff_auth import BffAuthenticationRejected, BffIdentity, consume_jti, verify_bff_token
from modal_service.config import Environment, feature_enabled, generation_enabled, limits_for
from modal_service.coordinator import JobCoordinator, JobOperation
from modal_service.costs import CostLimitExceeded, RateLimitExceeded
from modal_service.domain import DomainError, JobNotFound, JobRecord, JobState, PoseAlphaQualityError, PoseVisualConsistencyError, WorkflowMode
from modal_service.incubator import (
    NeutralVisualEncoder,
    VisualEncoderUnavailable,
    is_async_incubation,
    load_pinned_visual_encoder,
    master_selection_policy,
    pinned_encoder_status,
    rank_masters,
    shadow_ranking_observation,
    subject_hint,
)
from modal_service.inference_observability import InferenceObserver, trace_id_for_job
from modal_service.model_cache import (
    ModelCacheNotReady,
    ModelCacheSpec,
    activate_cached_revision,
    prepare_model_cache as prepare_cache,
    validate_active_cache,
)
from modal_service.persistent_runtime import PersistentPipelineRuntime
from modal_service.security import AuthenticationRejected, app_check_token, bearer_token, may_schedule_gpu, valid_firebase_claims
from modal_service.validation import ImageValidationError, validate_image
from modal_service.v2_contract import public_job
from modal_service.structured_observability import structured_event
from modal_service.templates import TemplatePackageError, validate_active_template_package

APP_NAME = os.getenv("GRU_MASCOT_APP_NAME", "gru-mascot")
FIREBASE_PROJECT_ID = "gru-mascote"
FIREBASE_PROJECT_NUMBER = "816774877835"
ASSET_ROOT = "/gru-assets"
MODEL_ROOT = "/gru-models"
ENVIRONMENT = Environment(os.getenv("GRU_MASCOT_ENV", Environment.DEVELOPMENT))
FIREBASE_SECRET_ENVIRONMENT = os.getenv("GRU_FIREBASE_SECRET_ENVIRONMENT") or None
RESOURCE_PREFIX = os.getenv("GRU_MASCOT_RESOURCE_PREFIX", "gru-mascot")
FIREBASE_SECRET_NAME = os.getenv("GRU_FIREBASE_SECRET_NAME", "gru-mascot-firebase-admin")
PULEIRO_BFF_SECRET_NAME = os.getenv("GRU_PULEIRO_BFF_SECRET_NAME", "gru-mascot-puleiro-bff")
LIMITS = limits_for(ENVIRONMENT)
GPU_GENERATION_ENABLED = generation_enabled(ENVIRONMENT, os.getenv("GPU_GENERATION_ENABLED"))
REGISTRATION_ENABLED = feature_enabled(os.getenv("REGISTRATION_ENABLED"), default=True)
MASTER_GENERATION_ENABLED = feature_enabled(os.getenv("MASTER_GENERATION_ENABLED"))
POSE_GENERATION_ENABLED = feature_enabled(os.getenv("POSE_GENERATION_ENABLED"))
INCUBATOR_FLOW_ENABLED = feature_enabled(os.getenv("INCUBATOR_FLOW_ENABLED"))
INCUBATOR_AUTO_RANKING_ENABLED = feature_enabled(os.getenv("INCUBATOR_AUTO_RANKING_ENABLED"))
CURRENT_REQUEST_ID: ContextVar[str] = ContextVar("modal_request_id", default="")
MASTER_GPU = "H100"
QWEN_MODEL_ID = "Qwen/Qwen-Image-Edit-2511"
QWEN_MODEL_REVISION = "6f3ccc0b56e431dc6a0c2b2039706d7d26f22cb9"
LIGHTNING_MODEL_ID = "lightx2v/Qwen-Image-Edit-2511-Lightning"
LIGHTNING_MODEL_REVISION = "d74eba145674fd7e31b949324e148e21e7118abd"
LIGHTNING_WEIGHT = "Qwen-Image-Edit-2511-Lightning-4steps-V1.0-fp32.safetensors"
MASTER_SEEDS = (0, 1, 2)
# QwenImageEditPlusPipeline ignores negative_prompt unless true_cfg_scale > 1.
# Keep the value deliberately close to one to activate CFG without making it
# the dominant source of pose composition; the positive prompt and QC gates
# remain the primary controls.
POSE_TRUE_CFG_SCALE = 1.1
SCHEDULER_CONFIG = {
    "base_image_seq_len": 256,
    "base_shift": 1.0986122886681098,
    "invert_sigmas": False,
    "max_image_seq_len": 8192,
    "max_shift": 1.0986122886681098,
    "num_train_timesteps": 1000,
    "shift": 1.0,
    "shift_terminal": None,
    "stochastic_sampling": False,
    "time_shift_type": "exponential",
    "use_beta_sigmas": False,
    "use_dynamic_shifting": True,
    "use_exponential_sigmas": False,
    "use_karras_sigmas": False,
}
WORKER_SCALEDOWN_SECONDS = 45
MASTER_RECONCILE_AFTER_SECONDS = 15
MASTER_STALE_AFTER_SECONDS = 300
WEB_POSE_CATALOG_VERSION = "web-poses-v1"
PERSISTENT_WORKER_MAX_CONTAINERS = 1
MODEL_CACHE_SPEC = ModelCacheSpec(
    model_id=QWEN_MODEL_ID,
    model_revision=QWEN_MODEL_REVISION,
    lora_id=LIGHTNING_MODEL_ID,
    lora_revision=LIGHTNING_MODEL_REVISION,
    lora_weight=LIGHTNING_WEIGHT,
)


def inference_config_hash() -> str:
    payload = {
        "model_id": QWEN_MODEL_ID,
        "model_revision": QWEN_MODEL_REVISION,
        "lora_id": LIGHTNING_MODEL_ID,
        "lora_revision": LIGHTNING_MODEL_REVISION,
        "lora_weight": LIGHTNING_WEIGHT,
        "dtype": "bfloat16",
        "steps": 4,
        "seeds": MASTER_SEEDS,
        "true_cfg_scale": 1.0,
        "negative_prompt": " ",
        "prompt": MASTER_PROMPT,
        "scheduler": SCHEDULER_CONFIG,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()[:16]


class CreateJobRequest(BaseModel):
    image_base64: str = Field(min_length=1, max_length=14_000_000)
    content_type: str | None = None
    pose_choices: dict[str, str] = Field(default_factory=lambda: dict(DEFAULT_POSE_CHOICES))


class SubjectIdentityRequest(BaseModel):
    category: Literal["human", "animal", "object", "other"]
    label: str = Field(min_length=1, max_length=64)
    species: str | None = Field(default=None, max_length=64)
    confirmed: bool


class CreateJobV2Request(BaseModel):
    image_base64: str = Field(min_length=1, max_length=14_000_000)
    content_type: str | None = None
    attempt_id: str = Field(pattern=r"^[A-Za-z0-9:_-]{1,160}$")
    subject_identity: SubjectIdentityRequest


class PoseGenerationV2Request(BaseModel):
    pose_choices: dict[str, str]
    catalog_version: str | None = None


class MascotConfigurationV2Request(BaseModel):
    display_name: str | None = Field(default=None, min_length=2, max_length=32)
    pose_choices: dict[str, str] | None = None
    configuration_revision: int = Field(ge=0)


class SubjectHintV2Request(BaseModel):
    image_base64: str = Field(min_length=1, max_length=14_000_000)
    content_type: str | None = None
    selected_category: Literal["human", "animal", "object", "other"]


class SubjectHintPayload(BaseModel):
    version: str
    suggestedCategory: Literal["human", "animal", "uncertain"]
    confidenceBand: Literal["low", "medium", "high"]
    requiresConfirmation: bool
    overrideConfirmed: bool = False


class CreateIncubationV2Request(CreateJobV2Request):
    pose_choices: dict[str, str]
    subject_hint: SubjectHintPayload | None = None


def _normalized_subject_identity(request: SubjectIdentityRequest) -> dict[str, object]:
    if not request.confirmed:
        raise DomainError("The subject identity must be confirmed before generation.")
    label = " ".join(request.label.split())
    species = " ".join((request.species or "").split()) or None
    if not label:
        raise DomainError("A confirmed subject label is required.")
    if not _safe_identity_text(label) or (species and not _safe_identity_text(species)):
        raise DomainError("Subject identity must be a short description, not an instruction.")
    if request.category == "animal" and not species:
        raise DomainError("A confirmed animal species is required.")
    if request.category != "animal":
        species = None
    return {"category": request.category, "label": label, "species": species}


def _safe_identity_text(value: str) -> bool:
    punctuation = " .,'()/_-"
    return all(character.isalnum() or character in punctuation for character in value)


def _normalized_display_name(value: str) -> str:
    normalized = " ".join(value.split())
    allowed = " .'-"
    if not 2 <= len(normalized) <= 32 or not all(character.isalnum() or character in allowed for character in normalized):
        error = DomainError("Mascot name must contain 2 to 32 letters, numbers, spaces, apostrophes, hyphens, or periods.")
        error.code = "INVALID_DISPLAY_NAME"
        raise error
    return normalized


def _safe_correlation_id(value: str | None) -> str | None:
    if not value or not 8 <= len(value) <= 64:
        return None
    return value if all(character.isalnum() or character in "_:-" for character in value) else None


def _safe_operation_id(value: str | None) -> str | None:
    return _safe_correlation_id(value)


def _pose_operation_fingerprint(identity: BffIdentity, job: JobRecord, choices: dict[str, str]) -> str:
    payload = {
        "owner": identity.user_id,
        "attempt": identity.attempt_id,
        "job": job.job_id,
        "master": job.master_id,
        "choices": choices,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _trace_id_for_record(job: JobRecord) -> str:
    return job.correlation_id or trace_id_for_job(job.job_id)


class ApproveMasterRequest(BaseModel):
    master_id: str = Field(pattern=r"^master_[1-4]$")


class PoseRequest(BaseModel):
    pose_id: str = Field(pattern=r"^pose_[0-9]{2}$")

api_image = (
    modal.Image.debian_slim(python_version="3.12")
    .env(
        {
            "GRU_MASCOT_APP_NAME": APP_NAME,
            "GRU_MASCOT_RESOURCE_PREFIX": RESOURCE_PREFIX,
            "GRU_MASCOT_ENV": ENVIRONMENT.value,
            "GPU_GENERATION_ENABLED": "true" if GPU_GENERATION_ENABLED else "false",
            "REGISTRATION_ENABLED": "true" if REGISTRATION_ENABLED else "false",
            "MASTER_GENERATION_ENABLED": "true" if MASTER_GENERATION_ENABLED else "false",
            "POSE_GENERATION_ENABLED": "true" if POSE_GENERATION_ENABLED else "false",
            "INCUBATOR_FLOW_ENABLED": "true" if INCUBATOR_FLOW_ENABLED else "false",
            "INCUBATOR_AUTO_RANKING_ENABLED": "true" if INCUBATOR_AUTO_RANKING_ENABLED else "false",
            "INCUBATOR_VISUAL_ENCODER_DIR": os.getenv("INCUBATOR_VISUAL_ENCODER_DIR", ""),
            "PULEIRO_BFF_JWT_ISSUER": os.getenv("PULEIRO_BFF_JWT_ISSUER", "puleiro-bff"),
            "PULEIRO_BFF_JWT_AUDIENCE": os.getenv("PULEIRO_BFF_JWT_AUDIENCE", "gru-modal"),
            "PULEIRO_BFF_JWT_MAX_TTL_SECONDS": os.getenv("PULEIRO_BFF_JWT_MAX_TTL_SECONDS", "120"),
        }
    )
    .pip_install(
        "fastapi[standard]>=0.115,<1",
        "pillow>=11,<12",
        "httpx>=0.28,<1",
        "google-auth>=2.38,<3",
        "firebase-admin>=6.6,<7",
        "PyJWT>=2.10,<3",
    )
)
incubator_image = api_image.pip_install(
    "numpy==2.1.3",
    "onnxruntime==1.20.1",
)
gpu_image = api_image.pip_install(
    "torch>=2.6,<3",
    "torchvision>=0.21,<1",
    "diffusers>=0.35",
    "transformers>=4.51",
    "accelerate>=1.6",
    "peft>=0.17,<1",
    "safetensors>=0.5",
)
cache_image = api_image.pip_install("huggingface_hub>=0.34,<1")
app = modal.App(APP_NAME)
assets = modal.Volume.from_name(f"{RESOURCE_PREFIX}-assets", create_if_missing=True)
models = modal.Volume.from_name(f"{RESOURCE_PREFIX}-models", create_if_missing=True)
jobs = modal.Dict.from_name(f"{RESOURCE_PREFIX}-jobs", create_if_missing=True)
idempotency = modal.Dict.from_name(f"{RESOURCE_PREFIX}-idempotency", create_if_missing=True)
usage = modal.Dict.from_name(f"{RESOURCE_PREFIX}-usage", create_if_missing=True)
firebase_admin_secret = modal.Secret.from_name(
    FIREBASE_SECRET_NAME,
    environment_name=FIREBASE_SECRET_ENVIRONMENT,
)
puleiro_bff_secret = modal.Secret.from_name(
    PULEIRO_BFF_SECRET_NAME,
    environment_name=FIREBASE_SECRET_ENVIRONMENT,
)


def _record_key(user_id: str, idempotency_key: str) -> str:
    return f"create:{user_id}:{idempotency_key}"


def _operation_key(user_id: str, operation: str) -> str:
    return f"operation:{user_id}:{operation}"


def _attempt_key(user_id: str, attempt_id: str) -> str:
    return f"attempt:{user_id}:{attempt_id}"


def _asset_path(job_id: str, folder: str, name: str) -> Path:
    return Path(ASSET_ROOT, folder, job_id, name)


def _delete_job_assets(job_id: str) -> int:
    deleted = 0
    for folder in ("original", "temporary", "masters_raw", "masters", "poses_raw", "poses", "consistency"):
        target = Path(ASSET_ROOT, folder, job_id)
        if target.exists():
            shutil.rmtree(target)
            deleted += 1
    return deleted


def _templates_installed() -> bool:
    try:
        validate_active_template_package(Path(ASSET_ROOT))
        return True
    except (OSError, ValueError, json.JSONDecodeError, TemplatePackageError):
        return False


def _active_pose_template(option_id: str) -> Path:
    package = validate_active_template_package(Path(ASSET_ROOT))
    return package.reference_for(option_id)


def _active_pose_template_version() -> str | None:
    """Expose only the installed template version; never an asset path."""
    try:
        return validate_active_template_package(Path(ASSET_ROOT)).version
    except (OSError, ValueError, json.JSONDecodeError, TemplatePackageError):
        return None


def _reload_template_assets() -> None:
    """Make an administrator-installed package visible to the long-lived API."""
    try:
        assets.reload()
    except Exception as error:  # A health probe must remain non-sensitive and fail closed.
        logging.info("pose_template_volume_reload_failed type=%s", type(error).__name__)


def _promote_private_directory(staging: Path, target: Path) -> None:
    """Replace a result set without exposing a partially written directory."""
    backup = target.with_name(f".{target.name}.previous")
    shutil.rmtree(backup, ignore_errors=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    had_previous = target.exists()
    if had_previous:
        target.replace(backup)
    try:
        staging.replace(target)
    except Exception:
        if had_previous and backup.exists() and not target.exists():
            backup.replace(target)
        raise
    else:
        shutil.rmtree(backup, ignore_errors=True)


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
    if job.state is JobState.AWAITING_MASTER_APPROVAL or job.master_id is not None:
        payload["masters"] = _master_references(job)
    return payload


def _refresh_result_assets(job: JobRecord) -> None:
    """Refresh a long-lived API container before exposing worker artifacts."""
    if job.state in {
        JobState.AWAITING_MASTER_APPROVAL,
        JobState.COMPLETED,
    } or job.master_id is not None:
        assets.reload()


def _master_references(job: JobRecord) -> list[dict[str, object]]:
    references: list[dict[str, object]] = []
    qc_by_master: dict[str, object] = {}
    qc_path = _asset_path(job.job_id, "masters", "qc.json")
    if qc_path.is_file():
        try:
            qc_by_master = json.loads(qc_path.read_text(encoding="utf-8")).get("masters", {})
        except (OSError, ValueError, TypeError):
            qc_by_master = {}
    # The public contract is exactly the three deterministic Master seeds.
    # Keep this derived list coupled to MASTER_SEEDS so an old fourth asset can
    # never leak into the Web or Android contracts.
    for index in range(1, len(MASTER_SEEDS) + 1):
        master_id = f"master_{index}"
        path = _asset_path(job.job_id, "masters", f"{master_id}.png")
        if path.is_file():
            reference: dict[str, object] = {
                "id": master_id,
                "download_path": f"/v1/mascot/jobs/{job.job_id}/masters/{master_id}",
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
            if isinstance(qc_by_master.get(master_id), dict):
                reference["qc"] = qc_by_master[master_id]
            references.append(reference)
    return references


def _pose_references(job: JobRecord) -> list[dict[str, object]]:
    manifest_path = _asset_path(job.job_id, "poses", "manifest.json")
    if job.state is not JobState.COMPLETED or not manifest_path.is_file():
        return []
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    references: list[dict[str, object]] = []
    for item in manifest.get("poses", []):
        references.append(
            {
                "id": str(item["poseId"]),
                "role": str(item["runtimeRole"]),
                "optionId": str(item["optionId"]),
                "label": str(item["name"]),
                "sha256": str(item["sha256"]),
                "qc": item.get("qc"),
            }
        )
    return references


def _pose_set_qc(job: JobRecord, poses: list[dict[str, object]]) -> dict[str, object]:
    from modal_service.image_processing import pose_set_visual_consistency_qc

    return pose_set_visual_consistency_qc(poses)


def _public_job_with_assets(job: JobRecord) -> dict[str, object]:
    masters = _master_references(job)
    poses = _pose_references(job)
    return public_job(job, masters, poses, _pose_set_qc(job, poses))


def _deserialize(record: dict[str, object]) -> JobRecord:
    # API responses may include presentation-only fields (for example, the
    # signed master references). Persisted JobRecord data must remain the sole
    # input to the domain object when a response is reconciled back into state.
    record_fields = {field.name for field in fields(JobRecord)}
    persisted = {key: value for key, value in record.items() if key in record_fields}
    return JobRecord(**(persisted | {"state": JobState(str(persisted["state"]))}))


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
    if not user_id.strip() or not idempotency_key.strip():
        raise DomainError("Verified user identity and idempotency key are required.")
    return user_id.strip(), idempotency_key.strip()


def utc_day_key() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).date().isoformat()


def _elapsed_ms(started: float) -> int:
    return max(0, int((time.monotonic() - started) * 1_000))


def _endpoint_name(request) -> str:
    endpoint = request.scope.get("endpoint")
    name = getattr(endpoint, "__name__", None)
    return str(name or "unmatched")[:64]


@app.function(image=api_image, max_containers=1)
@modal.concurrent(max_inputs=1)
def register_job(
    user_id: str,
    idempotency_key: str,
    source_key: str,
    pose_choices: dict[str, str] | None = None,
    subject_identity: dict[str, object] | None = None,
    registration_only: bool = False,
    attempt_id: str | None = None,
    correlation_id: str | None = None,
    workflow_mode: str = WorkflowMode.LEGACY_MANUAL.value,
    subject_hint_payload: dict[str, object] | None = None,
) -> dict[str, object]:
    try:
        coordinator = JobCoordinator(jobs, idempotency, usage, LIMITS, utc_day_key())
        job, created = coordinator.register(
            user_id,
            idempotency_key,
            source_key,
            pose_choices,
            subject_identity,
            registration_only=registration_only,
            attempt_id=attempt_id,
            correlation_id=correlation_id,
            workflow_mode=workflow_mode,
            subject_hint=subject_hint_payload,
        )
        if attempt_id:
            coordinator.idempotency[_attempt_key(user_id, attempt_id)] = job.job_id
        return {"job": _serialize(job), "created": created}
    except (DomainError, CostLimitExceeded, RateLimitExceeded) as error:
        return {"error_code": getattr(error, "code", "INVALID_REQUEST"), "error_message": str(error)}


@app.function(image=api_image, max_containers=1)
@modal.concurrent(max_inputs=1)
def consume_bff_jti(jti: str, expires_at: int) -> dict[str, object]:
    try:
        consume_jti(idempotency, jti, expires_at)
        return {"accepted": True}
    except BffAuthenticationRejected as error:
        return {"error_code": "BFF_TOKEN_REPLAYED", "error_message": str(error)}


@app.function(image=api_image, max_containers=1, volumes={ASSET_ROOT: assets})
def prepare_benchmark_job(benchmark_key: str) -> dict[str, object]:
    """Create a non-personal synthetic development job without bypassing coordination."""
    if ENVIRONMENT is not Environment.DEVELOPMENT:
        raise RuntimeError("Synthetic benchmark jobs are development-only.")
    from io import BytesIO
    from PIL import Image, ImageDraw

    canvas = Image.new("RGB", (1024, 1024), (225, 210, 180))
    draw = ImageDraw.Draw(canvas)
    draw.ellipse((220, 100, 804, 840), fill=(126, 91, 61), outline=(48, 38, 30), width=18)
    draw.ellipse((320, 260, 500, 440), fill=(250, 244, 220), outline=(48, 38, 30), width=12)
    draw.ellipse((524, 260, 704, 440), fill=(250, 244, 220), outline=(48, 38, 30), width=12)
    draw.ellipse((385, 315, 445, 375), fill=(30, 28, 25))
    draw.ellipse((579, 315, 639, 375), fill=(30, 28, 25))
    draw.polygon(((512, 390), (450, 490), (574, 490)), fill=(214, 154, 42))
    output = BytesIO()
    canvas.save(output, format="PNG", optimize=True)
    content = output.getvalue()
    digest = hashlib.sha256(content).hexdigest()
    coordinator = JobCoordinator(jobs, idempotency, usage, LIMITS, utc_day_key())
    job, created = coordinator.register("modal-benchmark", benchmark_key, f"synthetic/{digest}")
    if created:
        destination = _asset_path(job.job_id, "original", "source.bin")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
        assets.commit()
    coordinator.authorize_generation(job.job_id, "modal-benchmark", GPU_GENERATION_ENABLED)
    return {"job_id": job.job_id, "created": created, "source_bytes": len(content)}


@app.function(image=api_image, max_containers=1, volumes={ASSET_ROOT: assets})
@modal.concurrent(max_inputs=1)
def job_control(
    operation: str,
    job_id: str,
    user_id: str = "",
    attempt_id: str = "",
    master_id: str = "",
    call_id: str = "",
    outputs: list[bytes] | None = None,
    pose_choices: dict[str, str] | None = None,
    display_name: str | None = None,
    configuration_revision: int = 0,
    operation_id: str = "",
    operation_fingerprint: str = "",
    correlation_id: str = "",
    request_id: str = "",
    error_code: str = "",
    master_selection: dict[str, object] | None = None,
    shadow_ranking: dict[str, object] | None = None,
    lease_owner: str = "",
    lease_ttl_seconds: int = 90,
) -> dict[str, object]:
    try:
        coordinator = JobCoordinator(jobs, idempotency, usage, LIMITS, utc_day_key())
        command = JobOperation(operation)
        changed = False
        reserved = False
        if command is JobOperation.AUTHORIZE_GENERATION:
            changed = coordinator.authorize_generation(job_id, user_id, GPU_GENERATION_ENABLED)
            job = coordinator.get(job_id)
        elif command is JobOperation.START_MASTER:
            job, changed = coordinator.transition_if_active(job_id, JobState.VALIDATING_INPUT, JobState.GENERATING_MASTER)
        elif command is JobOperation.COMMIT_MASTER:
            assets.reload()
            job, changed = coordinator.commit_master_outputs(job_id, _verify_master_outputs)
        elif command is JobOperation.RECONCILE_MASTER:
            job = coordinator.get(job_id)
            changed = False
            if job.state is JobState.GENERATING_MASTER:
                assets.reload()
                if _master_outputs_ready(job):
                    job, changed = coordinator.commit_master_outputs(job_id, _verify_master_outputs)
                elif _job_age_seconds(job) >= MASTER_STALE_AFTER_SECONDS:
                    job, changed = coordinator.fail_stale_master(job_id, "MASTER_WORKER_STALE")
        elif command is JobOperation.FAIL_MASTER:
            job, changed = coordinator.transition_if_active(
                job_id, JobState.GENERATING_MASTER, JobState.FAILED, "MASTER_GENERATION_FAILED"
            )
        elif command is JobOperation.RECORD_GPU_CALL:
            job, changed = coordinator.record_gpu_call(job_id, call_id)
        elif command is JobOperation.RESERVE_POSE_GPU_CALL:
            job, changed = coordinator.reserve_pose_gpu_call(job_id)
        elif command is JobOperation.RECORD_POSE_GPU_CALL:
            job, changed = coordinator.record_pose_gpu_call(job_id, call_id)
        elif command is JobOperation.APPROVE_MASTER:
            job, changed = coordinator.approve_master(job_id, user_id, master_id, POSE_PROMPT_VERSION)
        elif command is JobOperation.AUTO_SELECT_MASTER:
            job, changed = coordinator.auto_select_master(job_id, master_selection or {}, POSE_PROMPT_VERSION)
        elif command is JobOperation.SELECT_INCUBATOR_MASTER:
            job, changed = coordinator.select_incubator_master(job_id, user_id, master_id, POSE_PROMPT_VERSION)
        elif command is JobOperation.RECORD_SHADOW_RANKING:
            job, changed = coordinator.record_shadow_ranking(job_id, shadow_ranking or {})
        elif command is JobOperation.UPDATE_CONFIGURATION:
            job, changed = coordinator.update_configuration(
                job_id,
                user_id,
                display_name,
                pose_choices,
                configuration_revision,
            )
        elif command is JobOperation.START_POSES:
            job, changed = coordinator.start_pose_generation(job_id, pose_choices or dict(DEFAULT_POSE_CHOICES))
        elif command is JobOperation.ENQUEUE_POSES:
            job, changed, reserved = coordinator.enqueue_pose_generation(
                job_id,
                user_id,
                pose_choices or dict(DEFAULT_POSE_CHOICES),
                operation_id,
                operation_fingerprint,
                _safe_correlation_id(correlation_id),
                _safe_correlation_id(request_id),
            )
        elif command is JobOperation.COMMIT_POSES:
            assets.reload()
            job, changed = coordinator.commit_pose_outputs(job_id, _verify_pose_outputs)
        elif command is JobOperation.FAIL_POSES:
            job, changed = coordinator.fail_pose_generation(job_id, error_code or "POSE_GENERATION_FAILED")
        elif command is JobOperation.FAIL_INCUBATION:
            job, changed = coordinator.fail_incubation(job_id, error_code or "INCUBATION_FAILED")
        elif command is JobOperation.CLAIM_INCUBATION_LEASE:
            job, changed = coordinator.claim_incubation_lease(job_id, lease_owner, lease_ttl_seconds)
        elif command is JobOperation.HEARTBEAT_INCUBATION:
            job, changed = coordinator.heartbeat_incubation(job_id, lease_owner, lease_ttl_seconds)
        elif command is JobOperation.RELEASE_INCUBATION_LEASE:
            job, changed = coordinator.release_incubation_lease(job_id, lease_owner)
        elif command is JobOperation.CANCEL:
            job, changed = coordinator.cancel(job_id, user_id)
        elif command is JobOperation.DELETE:
            receipt_key = f"deleted:{job_id}"
            try:
                job = coordinator.get(job_id)
                coordinator.ensure_owner(job, user_id)
            except JobNotFound:
                receipt = idempotency.get(receipt_key)
                if receipt == {"user_id": user_id, "attempt_id": attempt_id}:
                    return {"deleted": True, "idempotent_replay": True, "job_id": job_id}
                raise
            asset_groups_deleted = _delete_job_assets(job_id)
            assets.commit()
            coordinator.delete(job_id, user_id)
            idempotency[receipt_key] = {"user_id": user_id, "attempt_id": attempt_id}
            return {
                "deleted": True,
                "idempotent_replay": False,
                "job_id": job_id,
                "asset_groups_deleted": asset_groups_deleted,
            }
        else:  # StrEnum exhaustiveness guard.
            raise DomainError("Unsupported job operation.")
        return {"job": _serialize(job), "changed": changed, "reserved": reserved}
    except (DomainError, CostLimitExceeded, RateLimitExceeded) as error:
        return {"error_code": getattr(error, "code", "INVALID_REQUEST"), "error_message": str(error)}


def _master_schedule_event(
    event: str,
    job: JobRecord,
    *,
    result: str | None = None,
    duration_ms: int | None = None,
    safe_error_code: str | None = None,
) -> None:
    structured_event(
        event,
        environment=ENVIRONMENT.value,
        result=result,
        durationMs=duration_ms,
        puleiroTraceId=_trace_id_for_record(job),
        attemptId=job.attempt_id,
        jobId=job.job_id,
        safeErrorCode=safe_error_code,
    )


def _master_remote_step(job: JobRecord, event: str, unavailable_code: str, operation) -> dict[str, object]:
    try:
        result = operation()
        _raise_guard_error(result)
        return result
    except GuardRejected as error:
        _master_schedule_event(event, job, result="rejected", safe_error_code=error.code)
        raise
    except Exception:
        _master_schedule_event(event, job, result="failure", safe_error_code=unavailable_code)
        raise GuardRejected(unavailable_code, "The master generation service is temporarily unavailable.") from None


def _master_generation_enabled() -> bool:
    return GPU_GENERATION_ENABLED and MASTER_GENERATION_ENABLED


def _pose_generation_enabled() -> bool:
    return GPU_GENERATION_ENABLED and POSE_GENERATION_ENABLED


def _require_master_generation_enabled() -> None:
    if not _master_generation_enabled():
        raise GuardRejected("GENERATION_DISABLED", "Master generation is disabled.")


def _require_pose_generation_enabled() -> None:
    if not _pose_generation_enabled():
        raise GuardRejected("POSE_GENERATION_DISABLED", "Pose generation is disabled.")


def _spawn_master_worker(job_id: str):
    """Single fail-closed boundary for every Master GPU invocation."""
    _require_master_generation_enabled()
    return QwenMasterWorker().generate.spawn(job_id)


def _spawn_pose_worker(job_id: str):
    """Single fail-closed boundary for every pose GPU invocation."""
    _require_pose_generation_enabled()
    return QwenMasterWorker().generate_poses.spawn(job_id)


def _schedule_master(job: JobRecord, user_id: str) -> dict[str, object]:
    started_at = time.monotonic()
    _master_schedule_event("master_schedule_received", job)
    # This scheduler is shared by legacy routes and the async reconciler.
    # Reject before any cost reservation, keeping an incubator recoverable.
    _require_master_generation_enabled()
    _master_remote_step(job, "master_cache_checked", "MASTER_CACHE_UNAVAILABLE", model_cache_status.remote)
    authorization = _master_remote_step(
        job,
        "master_authorization_checked",
        "MASTER_AUTHORIZATION_UNAVAILABLE",
        lambda: job_control.remote(JobOperation.AUTHORIZE_GENERATION.value, job.job_id, user_id),
    )
    job_data = dict(authorization["job"])
    if not may_schedule_gpu(GPU_GENERATION_ENABLED, bool(authorization["changed"])):
        _master_schedule_event("master_schedule_replayed", job, result="replayed", duration_ms=_elapsed_ms(started_at))
        return job_data
    InferenceObserver(_trace_id_for_record(_deserialize(job_data))).event(
        "job_queued",
        {"cache_revision": MODEL_CACHE_SPEC.cache_revision, "gpu_type": MASTER_GPU},
    )
    try:
        function_call = _spawn_master_worker(job.job_id)
    except Exception:
        _master_schedule_event("master_worker_enqueue_failed", job, result="failure", safe_error_code="MASTER_WORKER_ENQUEUE_FAILED")
        raise GuardRejected("MASTER_WORKER_ENQUEUE_FAILED", "The master worker could not be queued.") from None
    recorded = _master_remote_step(
        job,
        "master_worker_record_checked",
        "MASTER_WORKER_RECORD_UNAVAILABLE",
        lambda: job_control.remote(JobOperation.RECORD_GPU_CALL.value, job.job_id, call_id=function_call.object_id),
    )
    _master_schedule_event("master_worker_spawned", job, result="spawned", duration_ms=_elapsed_ms(started_at))
    return dict(recorded["job"])


@app.function(image=incubator_image, volumes={ASSET_ROOT: assets, MODEL_ROOT: models}, max_containers=1)
@modal.concurrent(max_inputs=1)
def advance_async_incubation(job_id: str) -> dict[str, object]:
    """Advance persisted Master outputs to the single pose operation.

    The operation is CPU-only until the existing pose worker is spawned. A
    reserved pose call is never retried here: an uncertain/lost spawn remains
    visible and requires explicit owner action.
    """
    lease_owner = f"incubator-{secrets.token_hex(12)}"
    claimed = job_control.remote(
        JobOperation.CLAIM_INCUBATION_LEASE.value,
        job_id,
        lease_owner=lease_owner,
    )
    _raise_guard_error(claimed)
    if not bool(claimed["changed"]):
        return dict(claimed)
    try:
        job = _deserialize(dict(claimed["job"]))
        if not is_async_incubation(job):
            return {"job": _serialize(job), "changed": False}
        if job.state in {JobState.GENERATING_POSES, JobState.COMPLETED}:
            return {"job": _serialize(job), "changed": False}
        if job.state not in {JobState.AWAITING_MASTER_APPROVAL, JobState.CONSISTENCY_TEST}:
            raise DomainError("Async incubation cannot advance from the current state.")
        selected_job = job
        if job.state is JobState.AWAITING_MASTER_APPROVAL:
            if (job.master_selection or {}).get("decision") == "NEEDS_HUMAN_SELECTION":
                return {"job": _serialize(job), "changed": False, "deferred": True, "needsHumanSelection": True}
            assets.reload()
            references = _master_references(job)
            qc_by_master = {str(item["id"]): dict(item.get("qc") or {}) for item in references}
            candidates = {
                str(item["id"]): _asset_path(job_id, "masters", f"{item['id']}.png").read_bytes()
                for item in references
            }
            source = _asset_path(job_id, "original", "source.bin").read_bytes()
            try:
                selection = master_selection_policy(rank_masters(
                    source,
                    candidates,
                    qc_by_master,
                    str(job.subject_identity.get("category", "other")),
                    load_pinned_visual_encoder(),
                ))
            except (OSError, ValueError, VisualEncoderUnavailable):
                if not INCUBATOR_AUTO_RANKING_ENABLED:
                    structured_event(
                        "incubator_shadow_ranking_unavailable",
                        environment=ENVIRONMENT.value,
                        result="deferred",
                        jobId=job_id,
                        safeErrorCode="MASTER_SHADOW_RANKING_UNAVAILABLE",
                    )
                    return {"job": _serialize(job), "changed": False, "deferred": True, "shadow": True}
                failed = job_control.remote(
                    JobOperation.FAIL_INCUBATION.value,
                    job_id,
                    error_code="MASTER_AUTO_RANKING_FAILED",
                )
                _raise_guard_error(failed)
                return dict(failed)
            if not INCUBATOR_AUTO_RANKING_ENABLED:
                observation = shadow_ranking_observation(selection)
                observed = job_control.remote(
                    JobOperation.RECORD_SHADOW_RANKING.value,
                    job_id,
                    shadow_ranking=observation,
                )
                _raise_guard_error(observed)
                structured_event(
                    "incubator_master_ranked_shadow",
                    environment=ENVIRONMENT.value,
                    result="observed",
                    jobId=job_id,
                    **observation,
                )
                return {"job": dict(observed["job"]), "changed": False, "deferred": True, "shadow": True}
            if selection["decision"] == "RANKING_FAILED":
                failed = job_control.remote(
                    JobOperation.FAIL_INCUBATION.value,
                    job_id,
                    error_code="MASTER_AUTO_RANKING_FAILED",
                )
                _raise_guard_error(failed)
                return dict(failed)
            if selection["decision"] == "NEEDS_HUMAN_SELECTION":
                observed = job_control.remote(
                    JobOperation.RECORD_SHADOW_RANKING.value,
                    job_id,
                    shadow_ranking=selection,
                )
                _raise_guard_error(observed)
                return {"job": dict(observed["job"]), "changed": False, "deferred": True, "needsHumanSelection": True}
            selected = job_control.remote(
                JobOperation.AUTO_SELECT_MASTER.value,
                job_id,
                master_selection=selection,
            )
            _raise_guard_error(selected)
            selected_job = _deserialize(dict(selected["job"]))
        elif not job.master_selection:
            raise DomainError("Async incubation selection is incomplete.")
        # A deployment may leave a completed Master awaiting the separately
        # controlled pose capability. Keep it recoverable; the reconciler will
        # resume from this idempotent selection once the flags are enabled.
        if not _pose_generation_enabled():
            return {"job": _serialize(selected_job), "changed": False, "deferred": True}
        operation_id = f"incubator_pose_{hashlib.sha256(job_id.encode()).hexdigest()[:24]}"
        fingerprint = hashlib.sha256(
            json.dumps({"jobId": job_id, "poseChoices": selected_job.pose_choices}, sort_keys=True).encode()
        ).hexdigest()
        enqueued = job_control.remote(
            JobOperation.ENQUEUE_POSES.value,
            job_id,
            user_id=job.user_id,
            pose_choices=selected_job.pose_choices,
            operation_id=operation_id,
            operation_fingerprint=fingerprint,
            correlation_id=job.correlation_id or "",
            request_id="async-incubator",
        )
        _raise_guard_error(enqueued)
        if not bool(enqueued["reserved"]):
            return dict(enqueued)
        pose_call = _spawn_pose_worker(job_id)
        recorded = job_control.remote(
            JobOperation.RECORD_POSE_GPU_CALL.value,
            job_id,
            call_id=pose_call.object_id,
        )
        _raise_guard_error(recorded)
        return dict(recorded)
    finally:
        released = job_control.remote(
            JobOperation.RELEASE_INCUBATION_LEASE.value,
            job_id,
            lease_owner=lease_owner,
        )
        _raise_guard_error(released)


@app.function(
    image=incubator_image,
    schedule=modal.Period(minutes=1),
    volumes={ASSET_ROOT: assets},
    max_containers=1,
)
def reconcile_async_incubations() -> dict[str, int]:
    """Recover CPU-only transition gaps without repeating a GPU inference."""
    counters = {"examined": 0, "advanced": 0, "failed": 0}
    for job_id, record in jobs.items():
        try:
            job = _deserialize(dict(record))
            if not is_async_incubation(job) or job.state in {JobState.COMPLETED, JobState.FAILED, JobState.CANCELED}:
                continue
            counters["examined"] += 1
            if job.state in {JobState.REGISTERED, JobState.READY_FOR_GENERATION}:
                # A disabled flag defers this CPU reconciler path without
                # changing the job or reserving another GPU operation.
                if _master_generation_enabled():
                    scheduled = _schedule_master(job, job.user_id)
                    job = _deserialize(dict(scheduled))
                    counters["advanced"] += 1
            if job.state is JobState.GENERATING_MASTER:
                reconciled = job_control.remote(JobOperation.RECONCILE_MASTER.value, str(job_id))
                _raise_guard_error(reconciled)
                job = _deserialize(dict(reconciled["job"]))
            if job.state in {JobState.AWAITING_MASTER_APPROVAL, JobState.CONSISTENCY_TEST} and _pose_generation_enabled():
                if job.state is JobState.AWAITING_MASTER_APPROVAL and (job.master_selection or {}).get("decision") == "NEEDS_HUMAN_SELECTION":
                    continue
                advanced = advance_async_incubation.remote(str(job_id))
                _raise_guard_error(advanced)
                counters["advanced"] += int(bool(advanced.get("changed") or advanced.get("reserved")))
        except Exception as error:
            counters["failed"] += 1
            structured_event(
                "incubation_reconcile_failed",
                environment=ENVIRONMENT.value,
                result="failed",
                jobId=str(job_id),
                safeErrorCode=getattr(error, "code", "INCUBATION_RECONCILE_FAILED"),
            )
    return counters


@app.function(image=incubator_image, volumes={MODEL_ROOT: models}, max_containers=1)
def inspect_subject_hint_cpu(content: bytes, selected_category: str) -> dict[str, object]:
    """Best-effort CPU-only category warning; explicit user choice still wins."""
    try:
        scores = load_pinned_visual_encoder().classify(content)
    except VisualEncoderUnavailable:
        scores = NeutralVisualEncoder().classify(content)
    return subject_hint(selected_category, scores)


@app.function(image=incubator_image, volumes={MODEL_ROOT: models}, max_containers=1)
def visual_encoder_status() -> dict[str, object]:
    return pinned_encoder_status()


@app.function(image=incubator_image, volumes={MODEL_ROOT: models}, max_containers=1, timeout=120)
def benchmark_visual_encoder_cpu(content: bytes, iterations: int = 20) -> dict[str, object]:
    """Controlled CPU benchmark; it returns no image, embedding, or prompt data."""
    if not 1 <= iterations <= 100:
        raise ValueError("iterations must be between 1 and 100")
    import resource

    started = time.perf_counter()
    encoder = load_pinned_visual_encoder()
    load_ms = round((time.perf_counter() - started) * 1000, 2)
    samples: list[float] = []
    for _ in range(iterations):
        call_started = time.perf_counter()
        encoder.classify(content)
        samples.append((time.perf_counter() - call_started) * 1000)
    ordered = sorted(samples)
    percentile = lambda fraction: ordered[max(0, min(len(ordered) - 1, round((len(ordered) - 1) * fraction)))]
    return {
        "encoder": encoder.provenance(),
        "loadMs": load_ms,
        "iterations": iterations,
        "p50Ms": round(percentile(0.50), 2),
        "p95Ms": round(percentile(0.95), 2),
        "rssKiB": int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss),
    }


@app.function(image=api_image, volumes={MODEL_ROOT: models}, max_containers=1)
def model_cache_status() -> dict[str, object]:
    started = time.perf_counter()
    observer = InferenceObserver("cache_status")
    observer.event("model_cache_validation_start")
    try:
        cache = validate_active_cache(Path(MODEL_ROOT), MODEL_CACHE_SPEC)
        observer.event(
            "model_cache_validated",
            {
                "cache_revision": cache.cache_revision,
                "cache_validation_ms": observer.elapsed_ms(started),
                "outcome": "ready",
            },
        )
        return {"cache_revision": cache.cache_revision, "ready": True}
    except ModelCacheNotReady as error:
        observer.event(
            "model_cache_validated",
            {
                "cache_validation_ms": observer.elapsed_ms(started),
                "error_code": error.code,
                "outcome": "not_ready",
            },
        )
        return {"error_code": error.code, "error_message": "The model cache is not ready."}


@app.function(image=cache_image, volumes={MODEL_ROOT: models}, max_containers=1, timeout=3_600)
def prepare_model_cache() -> dict[str, object]:
    """Administrative CPU operation. It never requests a GPU."""
    from huggingface_hub import hf_hub_download, snapshot_download

    cache = prepare_cache(
        Path(MODEL_ROOT),
        MODEL_CACHE_SPEC,
        snapshot_download=snapshot_download,
        hf_hub_download=hf_hub_download,
    )
    models.commit()
    return {
        "cache_revision": cache.cache_revision,
        "expected_files": len(cache.expected_files),
        "expected_size": cache.expected_size,
        "ready": True,
    }


@app.function(image=api_image, volumes={MODEL_ROOT: models}, max_containers=1)
def activate_model_cache_revision(cache_revision: str) -> dict[str, object]:
    """Administrative rollback pointer. Previous cache artifacts remain intact."""
    activate_cached_revision(Path(MODEL_ROOT), cache_revision)
    models.commit()
    return {"cache_revision": cache_revision, "active": True}


@app.cls(
    image=gpu_image,
    gpu=MASTER_GPU,
    timeout=LIMITS.model_timeout_seconds,
    min_containers=0,
    max_containers=PERSISTENT_WORKER_MAX_CONTAINERS,
    buffer_containers=0,
    scaledown_window=WORKER_SCALEDOWN_SECONDS,
    volumes={ASSET_ROOT: assets, MODEL_ROOT: models},
)
@modal.concurrent(max_inputs=1)
class QwenMasterWorker:
    @modal.enter()
    def startup(self) -> None:
        self.loaded_at = time.perf_counter()
        self.container_observer = InferenceObserver(secrets.token_hex(6))
        self.container_observer.event("container_start", {"cold_start": True, "gpu_type": MASTER_GPU})
        self.runtime = PersistentPipelineRuntime(lambda: _load_qwen_pipeline(self.container_observer))
        self.runtime.start()
        self.container_observer.event(
            "worker_ready",
            {
                "cache_revision": MODEL_CACHE_SPEC.cache_revision,
                "container_start_ms": self.container_observer.elapsed_ms(self.loaded_at),
                "gpu_type": MASTER_GPU,
                "jobs_in_container": 0,
            },
        )

    @modal.method()
    def generate(self, job_id: str) -> None:
        """GPU boundary. One method call owns one job; the pipeline remains container-scoped."""
        observer = InferenceObserver(_trace_id_for_record(_get_job(job_id)))
        worker_started = observer.mark()
        next_job = self.runtime.jobs_processed + 1
        observer.event(
            "job_started",
            {
                "cold_start": next_job == 1,
                "container_reused": next_job > 1,
                "gpu_type": MASTER_GPU,
                "inference_config_hash": inference_config_hash(),
                "jobs_in_container": next_job,
                "worker_age_ms": observer.elapsed_ms(self.loaded_at),
            },
        )
        if next_job > 1:
            observer.event("container_reused", {"container_reused": True, "jobs_in_container": next_job})
        if not _master_generation_enabled():
            observer.event("job_failed", {"error_code": "GENERATION_DISABLED", "outcome": "blocked"})
            return
        started = job_control.remote(JobOperation.START_MASTER.value, job_id)
        _raise_guard_error(started)
        if not bool(started["changed"]):
            return
        job = _deserialize(dict(started["job"]))
        try:
            assets.reload()
            outputs = self.runtime.run(lambda pipeline: _generate_qwen_masters(job, pipeline, observer))
            _persist_master_outputs(job, outputs)
            committed = job_control.remote(JobOperation.COMMIT_MASTER.value, job_id)
            _raise_guard_error(committed)
            committed_job = _deserialize(dict(committed["job"]))
            if is_async_incubation(committed_job):
                try:
                    advance_async_incubation.remote(job_id)
                except Exception:
                    failed = job_control.remote(
                        JobOperation.FAIL_INCUBATION.value,
                        job_id,
                        error_code="INCUBATION_ADVANCE_FAILED",
                    )
                    _raise_guard_error(failed)
            observer.event(
                "job_completed",
                {
                    "jobs_in_container": self.runtime.jobs_processed,
                    "outputs": len(outputs),
                    "result_bytes": sum(len(output) for output in outputs),
                    "total_worker_ms": observer.elapsed_ms(worker_started),
                    "outcome": "success",
                },
            )
        except Exception as error:  # GPU libraries expose unstable exception classes.
            code = "WORKER_CORRUPTED" if not self.runtime.healthy else "JOB_LOCAL_FAILURE"
            observer.event(
                "job_failed",
                {
                    "error_code": code,
                    "error_type": type(error).__name__[:96],
                    "total_worker_ms": observer.elapsed_ms(worker_started),
                    "outcome": "failure",
                },
            )
            failed = job_control.remote(JobOperation.FAIL_MASTER.value, job_id)
            _raise_guard_error(failed)
            if bool(failed["changed"]):
                raise error

    @modal.method()
    def generate_poses(self, job_id: str) -> None:
        """Generate the three user-selected runtime poses from the approved Master."""
        job = _get_job(job_id)
        observer = InferenceObserver(_trace_id_for_record(job))
        worker_started = observer.mark()
        structured_event(
            "pose_worker_started",
            environment=ENVIRONMENT.value,
            result="started",
            puleiroTraceId=_trace_id_for_record(job),
            attemptId=job.attempt_id,
            operationId=job.pose_operation_id,
            requestId=job.pose_request_id,
            jobId=job_id,
            masterId=job.master_id,
        )
        if not _pose_generation_enabled():
            observer.event("pose_job_failed", {"error_code": "GENERATION_DISABLED", "outcome": "blocked"})
            structured_event(
                "pose_worker_failed",
                environment=ENVIRONMENT.value,
                result="blocked",
                puleiroTraceId=_trace_id_for_record(job),
                attemptId=job.attempt_id,
                operationId=job.pose_operation_id,
                requestId=job.pose_request_id,
                jobId=job_id,
                masterId=job.master_id,
                safeErrorCode="GENERATION_DISABLED",
            )
            return
        if job.state is not JobState.GENERATING_POSES:
            observer.event("pose_job_skipped", {"state": job.state.value, "outcome": "not_active"})
            return
        try:
            assets.reload()
            outputs = self.runtime.run(lambda pipeline: _generate_qwen_poses(job, pipeline, observer))
            _persist_pose_outputs(job, outputs)
            committed = job_control.remote(JobOperation.COMMIT_POSES.value, job_id)
            _raise_guard_error(committed)
            structured_event(
                "pose_assets_verified",
                environment=ENVIRONMENT.value,
                result="verified",
                puleiroTraceId=_trace_id_for_record(job),
                attemptId=job.attempt_id,
                operationId=job.pose_operation_id,
                requestId=job.pose_request_id,
                jobId=job_id,
                masterId=job.master_id,
            )
            structured_event(
                "pose_worker_completed",
                environment=ENVIRONMENT.value,
                result="completed",
                durationMs=observer.elapsed_ms(worker_started),
                puleiroTraceId=_trace_id_for_record(job),
                attemptId=job.attempt_id,
                operationId=job.pose_operation_id,
                requestId=job.pose_request_id,
                jobId=job_id,
                masterId=job.master_id,
            )
            structured_event(
                "pose_set_ready",
                environment=ENVIRONMENT.value,
                result="ready",
                durationMs=observer.elapsed_ms(worker_started),
                puleiroTraceId=_trace_id_for_record(job),
                attemptId=job.attempt_id,
                operationId=job.pose_operation_id,
                requestId=job.pose_request_id,
                jobId=job_id,
                masterId=job.master_id,
            )
            observer.event(
                "pose_job_completed",
                {
                    "outputs": len(outputs),
                    "total_worker_ms": observer.elapsed_ms(worker_started),
                    "outcome": "success",
                },
            )
        except Exception as error:
            structured_event(
                "pose_worker_failed",
                environment=ENVIRONMENT.value,
                result="failed",
                durationMs=observer.elapsed_ms(worker_started),
                puleiroTraceId=_trace_id_for_record(job),
                attemptId=job.attempt_id,
                operationId=job.pose_operation_id,
                requestId=job.pose_request_id,
                jobId=job_id,
                masterId=job.master_id,
                safeErrorCode=getattr(error, "code", "POSE_GENERATION_FAILED"),
            )
            observer.event(
                "pose_job_failed",
                {
                    "error_code": getattr(error, "code", "POSE_GENERATION_FAILED"),
                    "error_type": type(error).__name__[:96],
                    "total_worker_ms": observer.elapsed_ms(worker_started),
                    "outcome": "failure",
                },
            )
            failed = job_control.remote(
                JobOperation.FAIL_POSES.value,
                job_id,
                error_code=getattr(error, "code", "POSE_GENERATION_FAILED"),
            )
            _raise_guard_error(failed)
            if bool(failed["changed"]):
                raise error

    @modal.exit()
    def shutdown(self) -> None:
        jobs = getattr(getattr(self, "runtime", None), "jobs_processed", 0)
        observer = getattr(self, "container_observer", InferenceObserver("container_exit"))
        observer.event("container_shutdown", {"jobs_in_container": jobs})


def _load_qwen_pipeline(observer: InferenceObserver):
    """Load the pinned local cache once during container startup."""
    import torch
    from diffusers import FlowMatchEulerDiscreteScheduler, QwenImageEditPlusPipeline
    from diffusers.models import QwenImageTransformer2DModel

    cache_started = observer.mark()
    observer.event("model_cache_validation_start")
    cache = validate_active_cache(Path(MODEL_ROOT), MODEL_CACHE_SPEC)
    observer.event(
        "model_cache_validated",
        {"cache_revision": cache.cache_revision, "cache_validation_ms": observer.elapsed_ms(cache_started)},
    )
    model_started = observer.mark()
    observer.event("model_load_start", {"cache_revision": cache.cache_revision})
    transformer = QwenImageTransformer2DModel.from_pretrained(
        str(cache.model_snapshot),
        subfolder="transformer",
        torch_dtype=torch.bfloat16,
        local_files_only=True,
    )
    model_read_ms = observer.elapsed_ms(model_started)
    observer.event("model_load_completed", {"cache_revision": cache.cache_revision, "model_read_ms": model_read_ms})
    pipeline_started = observer.mark()
    observer.event("pipeline_build_start")
    scheduler = FlowMatchEulerDiscreteScheduler.from_config(SCHEDULER_CONFIG)
    pipeline = QwenImageEditPlusPipeline.from_pretrained(
        str(cache.model_snapshot),
        transformer=transformer,
        scheduler=scheduler,
        torch_dtype=torch.bfloat16,
        local_files_only=True,
    )
    observer.event("pipeline_build_completed", {"pipeline_build_ms": observer.elapsed_ms(pipeline_started)})
    lora_started = observer.mark()
    pipeline.load_lora_weights(str(cache.lora_file))
    observer.event("lora_load_completed", {"lora_load_ms": observer.elapsed_ms(lora_started)})
    cuda_started = observer.mark()
    observer.event("cuda_transfer_start", {"gpu_type": MASTER_GPU})
    pipeline = pipeline.to("cuda")
    observer.event(
        "cuda_transfer_completed",
        {"cuda_transfer_ms": observer.elapsed_ms(cuda_started), "gpu_type": MASTER_GPU},
    )
    return pipeline


def _generate_qwen_masters(job: JobRecord, pipeline, observer: InferenceObserver) -> list[bytes]:
    """Generate the same three Lightning Masters without rebuilding the pipeline."""
    from io import BytesIO

    import torch
    from PIL import Image

    source_bytes = _asset_path(job.job_id, "original", "source.bin").read_bytes()
    source = Image.open(BytesIO(source_bytes)).convert("RGB")
    source.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
    torch.cuda.reset_peak_memory_stats()
    outputs: list[bytes] = []
    try:
        for seed in MASTER_SEEDS:
            inference_started = observer.mark()
            observer.event("master_generation_started", {"master_index": seed})
            generated = pipeline(
                image=[source],
                prompt=_master_prompt(job),
                negative_prompt=build_master_negative_prompt(job.subject_identity),
                true_cfg_scale=1.0,
                generator=torch.Generator("cuda").manual_seed(seed),
                num_inference_steps=4,
            ).images[0]
            try:
                buffer = BytesIO()
                generated.save(buffer, format="PNG")
                outputs.append(buffer.getvalue())
            finally:
                generated.close()
            observer.event(
                "master_generated",
                {
                    "generation_ms": observer.elapsed_ms(inference_started),
                    "master_index": seed,
                    "result_bytes": len(outputs[-1]),
                },
            )
        observer.event(
            "generation_completed",
            {
                "gpu_peak_memory_bytes": int(torch.cuda.max_memory_allocated()),
                "outputs": len(outputs),
                "source_bytes": len(source_bytes),
                "source_height": source.height,
                "source_width": source.width,
            },
        )
        return outputs
    finally:
        source.close()


def _generate_qwen_poses(
    job: JobRecord,
    pipeline,
    observer: InferenceObserver,
) -> dict[str, bytes]:
    from io import BytesIO

    import torch
    from PIL import Image

    if job.master_id is None:
        raise DomainError("An approved Master is required for pose generation.")
    master_bytes = _asset_path(job.job_id, "masters", f"{job.master_id}.png").read_bytes()
    source = Image.open(BytesIO(master_bytes)).convert("RGBA")
    # Inference expects RGB. Preserve the approved alpha edge by composing it
    # onto the canonical neutral backdrop instead of flattening it to black.
    master = Image.new("RGBA", source.size, (244, 238, 222, 255))
    master.alpha_composite(source)
    source.close()
    master = master.convert("RGB")
    master.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
    option_seeds = {option.option_id: 100 + index for index, option in enumerate(POSE_OPTIONS)}
    outputs: dict[str, bytes] = {}
    try:
        for role in ("normal", "listening", "transcribing"):
            option = pose_option(job.pose_choices[role])
            template_path = _active_pose_template(option.option_id)
            with Image.open(template_path) as template_source:
                pose_reference = template_source.convert("RGB")
            started = observer.mark()
            try:
                observer.event(
                    "pose_generation_started",
                    {"pose_role": role, "pose_option": option.option_id, "template_reference": "loaded"},
                )
                generated = pipeline(
                    image=[master, pose_reference],
                    prompt=build_pose_prompt(job.subject_identity, role, option),
                    negative_prompt=build_pose_negative_prompt(job.subject_identity, role),
                    true_cfg_scale=POSE_TRUE_CFG_SCALE,
                    generator=torch.Generator("cuda").manual_seed(option_seeds[option.option_id]),
                    num_inference_steps=4,
                ).images[0]
                try:
                    buffer = BytesIO()
                    generated.save(buffer, format="PNG")
                    outputs[option.option_id] = buffer.getvalue()
                finally:
                    generated.close()
            finally:
                pose_reference.close()
            observer.event(
                "pose_generated",
                {
                    "generation_ms": observer.elapsed_ms(started),
                    "pose_role": role,
                    "pose_option": option.option_id,
                    "result_bytes": len(outputs[option.option_id]),
                },
            )
        return outputs
    finally:
        master.close()


def _master_prompt(job: JobRecord) -> str:
    return build_master_prompt(job.subject_identity)


def _persist_master_outputs(job: JobRecord, outputs: list[bytes]) -> None:
    from modal_service.image_processing import master_transparency_qc, remove_connected_flat_background

    if not outputs:
        raise DomainError("Master generation returned no images.")
    observer = InferenceObserver(_trace_id_for_record(job))
    postprocess_started = observer.mark()
    raw_target = Path(ASSET_ROOT, "masters_raw", job.job_id)
    raw_target.mkdir(parents=True, exist_ok=True)
    for index, content in enumerate(outputs, start=1):
        raw_path = raw_target / f"master_{index}.png"
        if not raw_path.exists():
            raw_path.write_bytes(content)
    normalized = [remove_connected_flat_background(content) for content in outputs]
    qc = {f"master_{index}": master_transparency_qc(content) for index, content in enumerate(normalized, start=1)}
    if any(result.get("status") != "passed" for result in qc.values()):
        assets.commit()
        raise DomainError("Master alpha quality verification failed.")
    observer.event(
        "postprocess_completed",
        {"outputs": len(normalized), "postprocess_ms": observer.elapsed_ms(postprocess_started)},
    )
    write_started = observer.mark()
    staging = Path(ASSET_ROOT, "temporary", job.job_id, "masters")
    target = Path(ASSET_ROOT, "masters", job.job_id)
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True, exist_ok=True)
    for index, content in enumerate(normalized, start=1):
        destination = staging / f"master_{index}.png"
        destination.write_bytes(content)
    (staging / "qc.json").write_text(json.dumps({"masters": qc}, ensure_ascii=False), encoding="utf-8")
    _promote_private_directory(staging, target)
    assets.commit()
    observer.event(
        "result_write_completed",
        {
            "outputs": len(normalized),
            "result_bytes": sum(len(content) for content in normalized),
            "result_write_ms": observer.elapsed_ms(write_started),
        },
    )


def _persist_pose_outputs(job: JobRecord, outputs: dict[str, bytes]) -> None:
    from modal_service.image_processing import pose_set_visual_consistency_qc, pose_transparency_qc, remove_connected_flat_background

    expected_options = tuple(pose_option(job.pose_choices[role]) for role in ("normal", "listening", "transcribing"))
    if set(outputs) != {option.option_id for option in expected_options} or job.master_id is None:
        raise DomainError("Pose generation returned an incomplete result.")
    raw_target = Path(ASSET_ROOT, "poses_raw", job.job_id)
    raw_target.mkdir(parents=True, exist_ok=True)
    for option_id, content in outputs.items():
        raw_path = raw_target / f"{option_id}.png"
        if not raw_path.exists():
            raw_path.write_bytes(content)
    staging = Path(ASSET_ROOT, "temporary", job.job_id, "poses")
    target = Path(ASSET_ROOT, "poses", job.job_id)
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True, exist_ok=True)
    poses: list[dict[str, object]] = []
    pose_ids: dict[str, str] = {}
    qc: dict[str, object] = {}
    for index, option in enumerate(expected_options, start=1):
        pose_id = f"pose_{index:02d}"
        pose_ids[option.option_id] = pose_id
        filename = f"{pose_id}.png"
        # Pose derivatives retain the generator canvas for the set-level
        # framing QC. Masters keep the legacy tight-crop presentation path.
        content = remove_connected_flat_background(outputs[option.option_id], crop=False)
        result = pose_transparency_qc(content)
        qc[pose_id] = result
        if result.get("status") != "passed":
            shutil.rmtree(staging, ignore_errors=True)
            assets.commit()
            raise PoseAlphaQualityError("Pose alpha quality verification failed.")
        (staging / filename).write_bytes(content)
        poses.append(
            {
                "poseId": pose_id,
                "runtimeRole": option.role,
                "optionId": option.option_id,
                "name": option.label,
                "fileName": filename,
                "sha256": hashlib.sha256(content).hexdigest(),
                "qc": result,
            }
        )
    pose_set_qc = pose_set_visual_consistency_qc(poses)
    if pose_set_qc.get("status") != "passed":
        shutil.rmtree(staging, ignore_errors=True)
        assets.commit()
        raise PoseVisualConsistencyError("Pose set visual consistency verification failed.")
    manifest = {
        "poseSetId": job.job_id,
        "masterId": job.master_id,
        "version": POSE_TEMPLATE_VERSION,
        "modelVersion": job.model_version,
        "promptVersion": POSE_PROMPT_VERSION,
        "idlePoseId": pose_ids[job.pose_choices["normal"]],
        "listeningPoseId": pose_ids[job.pose_choices["listening"]],
        "transcribingPoseId": pose_ids[job.pose_choices["transcribing"]],
        "poses": poses,
        "poseSetQc": pose_set_qc,
    }
    (staging / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    (staging / "qc.json").write_text(json.dumps({"poses": qc, "poseSetQc": pose_set_qc}, ensure_ascii=False), encoding="utf-8")
    _promote_private_directory(staging, target)
    assets.commit()


def _load_raw_pose_outputs(job: JobRecord) -> dict[str, bytes]:
    """Load exactly the three reserved private raws; reject partial or extra sets."""
    expected_options = tuple(pose_option(job.pose_choices[role]) for role in ("normal", "listening", "transcribing"))
    raw_root = Path(ASSET_ROOT, "poses_raw", job.job_id)
    expected_ids = {option.option_id for option in expected_options}
    actual_ids = {path.stem for path in raw_root.glob("*.png")} if raw_root.is_dir() else set()
    if actual_ids != expected_ids:
        raise DomainError("Raw pose recovery requires exactly the reserved three outputs.")
    return {option.option_id: (raw_root / f"{option.option_id}.png").read_bytes() for option in expected_options}


def _verify_pose_outputs(job: JobRecord) -> None:
    manifest = _asset_path(job.job_id, "poses", "manifest.json")
    if not manifest.is_file():
        raise DomainError("Pose result metadata is unavailable.")
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    poses = payload.get("poses", [])
    expected_ids = {"pose_01", "pose_02", "pose_03"}
    expected_roles = {"normal", "listening", "transcribing"}
    actual_ids = {str(item.get("poseId")) for item in poses}
    actual_roles = {str(item.get("runtimeRole")) for item in poses}
    selected = {str(item.get("runtimeRole")): str(item.get("optionId")) for item in poses}
    if len(poses) != 3 or actual_ids != expected_ids or actual_roles != expected_roles:
        raise DomainError("Pose outputs are incomplete.")
    if selected != job.pose_choices:
        raise DomainError("Pose outputs do not match the reserved choices.")
    qc_path = _asset_path(job.job_id, "poses", "qc.json")
    try:
        qc_document = json.loads(qc_path.read_text(encoding="utf-8"))
        qc_payload = qc_document.get("poses", {})
    except (OSError, ValueError, TypeError) as error:
        raise DomainError("Pose alpha quality metadata is unavailable.") from error
    if set(qc_payload) != expected_ids:
        raise DomainError("Pose alpha quality metadata is incomplete.")
    for item in poses:
        path = _asset_path(job.job_id, "poses", Path(str(item["fileName"])).name)
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != item.get("sha256"):
            raise DomainError("Pose output checksum is invalid.")
        qc = item.get("qc")
        pose_id = str(item.get("poseId"))
        if (
            not isinstance(qc, dict)
            or qc.get("status") != "passed"
            or qc.get("sha256") != item.get("sha256")
            or qc_payload.get(pose_id) != qc
        ):
            raise DomainError("Pose alpha quality verification failed.")
    from modal_service.image_processing import pose_set_visual_consistency_qc

    expected_pose_set_qc = pose_set_visual_consistency_qc(poses)
    if (
        expected_pose_set_qc.get("status") != "passed"
        or payload.get("poseSetQc") != expected_pose_set_qc
        or qc_document.get("poseSetQc") != expected_pose_set_qc
    ):
        raise DomainError("Pose visual consistency verification failed.")


def _master_outputs_ready(job: JobRecord) -> bool:
    target = Path(ASSET_ROOT, "masters", job.job_id)
    expected = tuple(target / f"master_{index}.png" for index in range(1, len(MASTER_SEEDS) + 1))
    return all(path.is_file() and path.stat().st_size > 0 for path in expected)


def _verify_master_outputs(job: JobRecord) -> None:
    if not _master_outputs_ready(job):
        raise DomainError("Master outputs are incomplete.")
    qc_path = _asset_path(job.job_id, "masters", "qc.json")
    try:
        masters = json.loads(qc_path.read_text(encoding="utf-8")).get("masters", {})
    except (OSError, ValueError, TypeError) as error:
        raise DomainError("Master alpha quality metadata is unavailable.") from error
    expected = {f"master_{index}" for index in range(1, len(MASTER_SEEDS) + 1)}
    if set(masters) != expected or any(item.get("status") != "passed" for item in masters.values()):
        raise DomainError("Master alpha quality verification failed.")
    for master_id, qc in masters.items():
        path = _asset_path(job.job_id, "masters", f"{master_id}.png")
        if not path.is_file() or qc.get("sha256") != hashlib.sha256(path.read_bytes()).hexdigest():
            raise DomainError("Master alpha asset checksum is invalid.")


def _job_age_seconds(job: JobRecord) -> float:
    updated = datetime.fromisoformat(job.updated_at)
    if updated.tzinfo is None:
        updated = updated.replace(tzinfo=UTC)
    return max(0.0, (datetime.now(UTC) - updated).total_seconds())


def _should_reconcile_master(job: JobRecord) -> bool:
    return job.state is JobState.GENERATING_MASTER and _job_age_seconds(job) >= MASTER_RECONCILE_AFTER_SECONDS


@app.function(image=api_image, volumes={ASSET_ROOT: assets}, max_containers=1)
def normalize_master_assets(job_id: str) -> dict[str, object]:
    """Create alpha derivatives without mutating the private raw Master source."""
    from modal_service.image_processing import master_transparency_qc, remove_connected_flat_background

    if not job_id.startswith("job_") or not job_id[4:].isalnum() or len(job_id) > 96:
        raise ValueError("Invalid job identifier.")
    raw_target = Path(ASSET_ROOT, "masters_raw", job_id)
    source_target = raw_target if raw_target.is_dir() else Path(ASSET_ROOT, "masters", job_id)
    if source_target != raw_target:
        raw_target.mkdir(parents=True, exist_ok=True)
        for source in source_target.glob("master_[1-4].png"):
            raw_path = raw_target / source.name
            if not raw_path.exists():
                shutil.copy2(source, raw_path)
        source_target = raw_target
    target = Path(ASSET_ROOT, "masters", job_id)
    staging = Path(ASSET_ROOT, "temporary", job_id, "normalized-masters")
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True, exist_ok=True)
    updated: list[dict[str, object]] = []
    qc: dict[str, object] = {}
    canonical_paths = [source_target / f"master_{index}.png" for index in range(1, len(MASTER_SEEDS) + 1)]
    for path in canonical_paths:
        if not path.is_file():
            continue
        normalized = remove_connected_flat_background(path.read_bytes())
        result = master_transparency_qc(normalized)
        qc[path.stem] = result
        if result.get("status") == "passed":
            (staging / path.name).write_bytes(normalized)
        updated.append({"master_id": path.stem, "qc_status": result.get("status")})
    if not updated:
        raise ValueError("No Master assets found.")
    if any(result.get("status") != "passed" for result in qc.values()):
        shutil.rmtree(staging, ignore_errors=True)
        raise ValueError("Master alpha quality verification failed.")
    (staging / "qc.json").write_text(json.dumps({"masters": qc}, ensure_ascii=False), encoding="utf-8")
    shutil.rmtree(target, ignore_errors=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    staging.replace(target)
    assets.commit()
    return {"job_id": job_id, "masters": updated}


@app.function(
    image=api_image,
    volumes={ASSET_ROOT: assets},
    secrets=[firebase_admin_secret, puleiro_bff_secret],
    max_containers=1,
)
@modal.asgi_app()
def api():
    from fastapi import Depends, FastAPI, Header
    from fastapi.exceptions import RequestValidationError
    from fastapi.responses import JSONResponse
    import firebase_admin
    from firebase_admin import app_check as firebase_app_check
    from firebase_admin import credentials
    from google.auth.transport.requests import Request as GoogleRequest
    from google.oauth2 import id_token

    service = FastAPI(title="GRU Mascot API", docs_url=None, redoc_url=None)
    def ensure_firebase_admin() -> None:
        """Initialize Firebase only for legacy v1 requests.

        Modal v2 authenticates the Puleiro BFF with its short-lived service
        token and must remain independently startable in an isolated staging
        environment without copying production Firebase credentials.
        """
        try:
            firebase_admin.get_app()
            return
        except ValueError:
            pass
        credentials_json = os.environ.get("FIREBASE_ADMIN_CREDENTIALS_JSON")
        if not credentials_json:
            raise RuntimeError("Firebase Admin credentials are unavailable for legacy v1 authentication.")
        firebase_admin.initialize_app(credentials.Certificate(json.loads(credentials_json)))

    @service.middleware("http")
    async def request_observability(request, call_next):
        request_id = secrets.token_hex(6)
        request.state.request_id = request_id
        request_token = CURRENT_REQUEST_ID.set(request_id)
        correlation_id = _safe_correlation_id(request.headers.get("x-correlation-id"))
        operation_id = _safe_operation_id(request.headers.get("x-operation-id"))
        started = time.monotonic()
        try:
            response = await call_next(request)
        except Exception as error:
            structured_event(
                "http_request_failed",
                environment=ENVIRONMENT.value,
                result="failure",
                durationMs=_elapsed_ms(started),
                puleiroTraceId=correlation_id,
                operationId=operation_id,
                requestId=request_id,
                safeErrorCode=type(error).__name__,
            )
            CURRENT_REQUEST_ID.reset(request_token)
            raise
        response.headers["X-Request-ID"] = request_id
        if correlation_id:
            response.headers.setdefault("X-Correlation-Id", correlation_id)
        if operation_id:
            response.headers.setdefault("X-Operation-Id", operation_id)
        structured_event(
            "http_request_completed",
            environment=ENVIRONMENT.value,
            result="success" if response.status_code < 400 else "rejected",
            durationMs=_elapsed_ms(started),
            puleiroTraceId=correlation_id,
            operationId=operation_id,
            requestId=request_id,
            httpStatus=response.status_code,
        )
        CURRENT_REQUEST_ID.reset(request_token)
        return response

    @service.exception_handler(RequestValidationError)
    async def request_validation_error(_request, error: RequestValidationError):
        failures = ",".join(
            f"{'.'.join(str(item) for item in issue.get('loc', ()))}:{issue.get('type', 'invalid')}"
            for issue in error.errors()[:5]
        )
        logging.info("event=request_validation outcome=rejected failures=%s", failures[:300])
        return JSONResponse(
            status_code=422,
            content={"detail": {"code": "INVALID_REQUEST", "message": "The request format is invalid."}},
        )

    # These dependencies live inside the ASGI factory. Keep FastAPI markers in
    # defaults so postponed annotations cannot turn them into public query args.
    async def verified_user(authorization: str | None = Header(default=None)) -> str:
        try:
            token = bearer_token(authorization)
        except AuthenticationRejected as error:
            from fastapi import HTTPException
            raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": str(error)}) from error
        try:
            ensure_firebase_admin()
            claims = id_token.verify_firebase_token(token, GoogleRequest(), audience="gru-mascote")
            if not valid_firebase_claims(claims, FIREBASE_PROJECT_ID):
                raise ValueError("Unexpected Firebase token claims.")
            return str(claims.get("uid") or claims["sub"])
        except Exception as error:
            logging.info("firebase_token_rejected type=%s", type(error).__name__)
            from fastapi import HTTPException
            raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "A valid identity is required."}) from error

    async def verified_app_check(x_firebase_appcheck: str | None = Header(default=None)) -> None:
        try:
            token = app_check_token(x_firebase_appcheck)
        except AuthenticationRejected as error:
            from fastapi import HTTPException
            raise HTTPException(status_code=401, detail={"code": "APP_CHECK_REQUIRED", "message": str(error)}) from error
        try:
            ensure_firebase_admin()
            firebase_app_check.verify_token(token)
        except Exception as error:
            logging.info("firebase_app_check_rejected type=%s", type(error).__name__)
            from fastapi import HTTPException
            raise HTTPException(status_code=401, detail={"code": "APP_CHECK_REQUIRED", "message": "A valid app proof is required."}) from error

    async def cost_context(
        user_id: str = Depends(verified_user),
        _: None = Depends(verified_app_check),
        x_idempotency_key: str | None = Header(default=None),
    ) -> tuple[str, str]:
        return _request_context(user_id, x_idempotency_key or "")

    async def secure_user(
        user_id: str = Depends(verified_user),
        _: None = Depends(verified_app_check),
    ) -> str:
        return user_id

    async def verified_bff_identity(authorization: str | None = Header(default=None)) -> BffIdentity:
        try:
            token = bearer_token(authorization)
            identity = verify_bff_token(token, os.environ.get("PULEIRO_BFF_JWT_SECRET", ""))
            replay = consume_bff_jti.remote(identity.jti, identity.expires_at)
            if replay.get("error_code"):
                raise BffAuthenticationRejected("A BFF token cannot be replayed.")
            return identity
        except (AuthenticationRejected, BffAuthenticationRejected) as error:
            from fastapi import HTTPException
            raise HTTPException(
                status_code=401,
                detail={"code": "BFF_UNAUTHENTICATED", "message": "A valid BFF identity is required."},
            ) from error

    async def bff_operation_context(
        identity: BffIdentity = Depends(verified_bff_identity),
        x_idempotency_key: str | None = Header(default=None),
        x_operation_id: str | None = Header(default=None),
    ) -> tuple[BffIdentity, str, str]:
        if not x_idempotency_key or not x_idempotency_key.strip():
            from fastapi import HTTPException
            raise HTTPException(
                status_code=400,
                detail={"code": "IDEMPOTENCY_KEY_REQUIRED", "message": "An idempotency key is required."},
            )
        operation_id = _safe_operation_id(x_operation_id)
        if not operation_id:
            from fastapi import HTTPException
            raise HTTPException(
                status_code=400,
                detail={"code": "OPERATION_ID_REQUIRED", "message": "An operation id is required."},
            )
        return identity, x_idempotency_key.strip(), operation_id

    @service.get("/health")
    async def health() -> dict[str, object]:
        _reload_template_assets()
        templates_ready = _templates_installed()
        return {
            "service": APP_NAME,
            "environment": ENVIRONMENT.value,
            "generation_enabled": GPU_GENERATION_ENABLED,
            "registration_enabled": REGISTRATION_ENABLED,
            "master_generation_enabled": MASTER_GENERATION_ENABLED,
            "pose_generation_enabled": POSE_GENERATION_ENABLED,
            "templates_installed": templates_ready,
            "template_version": _active_pose_template_version(),
            "pose_preflight_ready": templates_ready,
            "pose_operational_ready": templates_ready and POSE_GENERATION_ENABLED and GPU_GENERATION_ENABLED,
            "model_configured": True,
            "pose_catalog_size": len(POSE_OPTIONS),
            "pose_catalog_version": POSE_TEMPLATE_VERSION,
        }

    @service.get("/v2/mascot/capabilities")
    async def capabilities_v2(identity: BffIdentity = Depends(verified_bff_identity)) -> dict[str, object]:
        del identity
        encoder = visual_encoder_status.remote()
        _reload_template_assets()
        templates_ready = _templates_installed()
        pose_reasons: list[str] = []
        if not POSE_GENERATION_ENABLED:
            pose_reasons.append("POSE_GENERATION_DISABLED")
        if not GPU_GENERATION_ENABLED:
            pose_reasons.append("GPU_GENERATION_DISABLED")
        if not templates_ready:
            pose_reasons.append("POSE_TEMPLATES_UNAVAILABLE")
        master_reasons = [] if MASTER_GENERATION_ENABLED and GPU_GENERATION_ENABLED else ["GENERATION_DISABLED"]
        return {
            "contractVersion": "v2",
            "master": {
                "ready": not master_reasons,
                "reasonCode": master_reasons[0] if master_reasons else None,
                "reasons": master_reasons,
                "modelVersion": "qwen-image-edit-2511",
                "promptVersion": MASTER_PROMPT_VERSION,
            },
            "poses": {
                "ready": not pose_reasons,
                "preflightReady": templates_ready,
                "reasonCode": pose_reasons[0] if pose_reasons else None,
                "reasons": pose_reasons,
                "catalogVersion": WEB_POSE_CATALOG_VERSION,
                "templateVersion": POSE_TEMPLATE_VERSION,
                "workerVersion": "qwen-image-edit-2511",
            },
            # Keep the published Web v2 capability shape: each runtime role
            # maps to its accepted option IDs. Labels remain in the local
            # presentation catalog and no client contract is replaced here.
            "poseCatalog": {
                role: [option.option_id for option in POSE_OPTIONS if option.role == role]
                for role in ("normal", "listening", "transcribing")
            },
            "incubator": {
                "ready": INCUBATOR_FLOW_ENABLED and INCUBATOR_AUTO_RANKING_ENABLED and bool(encoder["ready"]) and not master_reasons and not pose_reasons,
                "enabled": INCUBATOR_FLOW_ENABLED,
                "autoRankingEnabled": INCUBATOR_AUTO_RANKING_ENABLED,
                "shadowMode": INCUBATOR_FLOW_ENABLED and not INCUBATOR_AUTO_RANKING_ENABLED,
                "encoder": encoder,
                "workflowVersion": WorkflowMode.ASYNC_INCUBATOR_V1.value,
                "rankerVersion": encoder["masterRankerVersion"],
                "subjectHintVersion": encoder["subjectHintPolicyVersion"],
            },
        }

    @service.post("/v1/mascot/jobs", status_code=202)
    async def create_job(request: CreateJobRequest, context: tuple[str, str] = Depends(cost_context)):
        user_id, key = context
        try:
            pose_choices = validate_pose_choices(request.pose_choices)
            content = _decode_image(request.image_base64)
            _, _, _ = validate_image(content, request.content_type)
            digest = hashlib.sha256(content).hexdigest()
            registration = register_job.remote(user_id, key, f"original/{digest}", pose_choices)
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
        except ValueError as error:
            raise _api_error(DomainError("Invalid pose selection.")) from error

    @service.post("/v2/mascot/jobs", status_code=202)
    async def create_job_v2(
        request: CreateJobV2Request,
        context: tuple[BffIdentity, str, str] = Depends(bff_operation_context),
        x_correlation_id: str | None = Header(default=None),
    ):
        identity, key, _ = context
        if not REGISTRATION_ENABLED:
            from fastapi import HTTPException
            raise HTTPException(
                status_code=503,
                detail={"code": "REGISTRATION_DISABLED", "message": "Job registration is disabled."},
            )
        if request.attempt_id != identity.attempt_id:
            from fastapi import HTTPException
            raise HTTPException(
                status_code=403,
                detail={"code": "ATTEMPT_MISMATCH", "message": "The attempt does not belong to this identity."},
            )
        try:
            subject_identity = _normalized_subject_identity(request.subject_identity)
            content = _decode_image(request.image_base64)
            validate_image(content, request.content_type)
            digest = hashlib.sha256(content).hexdigest()
            registration = register_job.remote(
                identity.user_id,
                key,
                f"original/{digest}",
                subject_identity=subject_identity,
                registration_only=True,
                attempt_id=request.attempt_id,
                correlation_id=_safe_correlation_id(x_correlation_id),
            )
            _raise_guard_error(registration)
            job = _deserialize(dict(registration["job"]))
            destination = _asset_path(job.job_id, "original", "source.bin")
            if not destination.is_file() or hashlib.sha256(destination.read_bytes()).hexdigest() != digest:
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(content)
                assets.commit()
            return public_job(job) | {"idempotentReplay": not bool(registration["created"])}
        except (ImageValidationError, DomainError, CostLimitExceeded, RateLimitExceeded) as error:
            raise _api_error(error) from error

    @service.get("/v2/mascot/jobs")
    async def recover_job_v2(
        attempt_id: str,
        identity: BffIdentity = Depends(verified_bff_identity),
    ):
        if attempt_id != identity.attempt_id:
            raise _api_error(JobNotFound("Job was not found."))
        try:
            job_id = str(idempotency[_attempt_key(identity.user_id, attempt_id)])
            job = _get_job(job_id)
            _ensure_owner(job, identity.user_id)
            _refresh_result_assets(job)
            return _public_job_with_assets(job)
        except KeyError as error:
            raise _api_error(JobNotFound("Job was not found.")) from error
        except DomainError as error:
            raise _api_error(error) from error

    @service.get("/v2/mascot/jobs/{job_id}")
    async def read_job_v2(job_id: str, identity: BffIdentity = Depends(verified_bff_identity)):
        try:
            job = _get_job(job_id)
            _ensure_owner(job, identity.user_id)
            if is_async_incubation(job) and job.state is JobState.AWAITING_MASTER_APPROVAL and not job.master_selection:
                advanced = advance_async_incubation.remote(job_id)
                _raise_guard_error(advanced)
                job = _deserialize(dict(advanced["job"]))
            _refresh_result_assets(job)
            return _public_job_with_assets(job)
        except DomainError as error:
            raise _api_error(error) from error

    @service.post("/v2/mascot/subject-hint")
    async def inspect_subject_hint_v2(
        request: SubjectHintV2Request,
        identity: BffIdentity = Depends(verified_bff_identity),
    ):
        del identity
        try:
            content = _decode_image(request.image_base64)
            validate_image(content, request.content_type)
            return inspect_subject_hint_cpu.remote(content, request.selected_category)
        except (ImageValidationError, DomainError) as error:
            raise _api_error(error) from error

    @service.post("/v2/mascot/incubations", status_code=202)
    async def create_incubation_v2(
        request: CreateIncubationV2Request,
        context: tuple[BffIdentity, str, str] = Depends(bff_operation_context),
        x_correlation_id: str | None = Header(default=None),
    ):
        identity, key, _ = context
        if not INCUBATOR_FLOW_ENABLED:
            raise _api_error(GuardRejected("INCUBATOR_DISABLED", "Async incubation is disabled."))
        if request.attempt_id != identity.attempt_id:
            raise _api_error(JobNotFound("Job was not found."))
        try:
            selected_poses = validate_pose_choices(request.pose_choices)
            normalized_hint = request.subject_hint.model_dump() if request.subject_hint else None
            if normalized_hint and normalized_hint["requiresConfirmation"] and not normalized_hint["overrideConfirmed"]:
                raise GuardRejected("SUBJECT_MISMATCH_CONFIRMATION_REQUIRED", "Subject mismatch confirmation is required.")
            subject_identity = _normalized_subject_identity(request.subject_identity)
            content = _decode_image(request.image_base64)
            validate_image(content, request.content_type)
            digest = hashlib.sha256(content).hexdigest()
            registration = register_job.remote(
                identity.user_id,
                key,
                f"original/{digest}",
                pose_choices=selected_poses,
                subject_identity=subject_identity,
                registration_only=True,
                attempt_id=request.attempt_id,
                correlation_id=_safe_correlation_id(x_correlation_id),
                workflow_mode=WorkflowMode.ASYNC_INCUBATOR_V1.value,
                subject_hint_payload=normalized_hint,
            )
            _raise_guard_error(registration)
            job = _deserialize(dict(registration["job"]))
            destination = _asset_path(job.job_id, "original", "source.bin")
            if not destination.is_file() or hashlib.sha256(destination.read_bytes()).hexdigest() != digest:
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(content)
                assets.commit()
            # Registration is deliberately independent from paid worker
            # readiness. Keep the persisted egg recoverable while all
            # generation kill-switches are false; the reconciler will resume
            # this same job after explicit enablement.
            if not _master_generation_enabled():
                return public_job(job) | {"idempotentReplay": not bool(registration["created"])}
            scheduled = _schedule_master(job, identity.user_id)
            return public_job(_deserialize(scheduled)) | {"idempotentReplay": not bool(registration["created"])}
        except (ImageValidationError, DomainError, CostLimitExceeded, RateLimitExceeded, ValueError) as error:
            raise _api_error(error) from error

    @service.delete("/v2/mascot/jobs/{job_id}")
    async def delete_job_v2(
        job_id: str,
        context: tuple[BffIdentity, str, str] = Depends(bff_operation_context),
    ):
        identity, _, _ = context
        try:
            job = _get_job(job_id)
            _ensure_owner(job, identity.user_id)
            if job.attempt_id != identity.attempt_id:
                raise JobNotFound("Job was not found.")
            for call_id in (job.gpu_call_id, job.pose_gpu_call_id):
                if call_id and call_id != "reserved":
                    modal.FunctionCall.from_id(call_id).cancel()
            deleted = job_control.remote(JobOperation.DELETE.value, job_id, identity.user_id, identity.attempt_id)
            _raise_guard_error(deleted)
            structured_event(
                "job_deletion_completed",
                environment=ENVIRONMENT.value,
                result="deleted",
                puleiroTraceId=_trace_id_for_record(job),
                attemptId=identity.attempt_id,
                jobId=job_id,
            )
            return deleted
        except DomainError as error:
            raise _api_error(error) from error

    @service.post("/v2/mascot/jobs/{job_id}/master-generations", status_code=202)
    async def start_master_generation_v2(
        job_id: str,
        context: tuple[BffIdentity, str, str] = Depends(bff_operation_context),
    ):
        identity, _, _ = context
        try:
            job = _get_job(job_id)
            _ensure_owner(job, identity.user_id)
            _require_master_generation_enabled()
            return public_job(_deserialize(_schedule_master(job, identity.user_id)))
        except (DomainError, CostLimitExceeded, RateLimitExceeded) as error:
            raise _api_error(error) from error

    @service.post("/v2/mascot/jobs/{job_id}/masters/{master_id}/approve")
    async def approve_master_v2(
        job_id: str,
        master_id: str,
        context: tuple[BffIdentity, str, str] = Depends(bff_operation_context),
    ):
        identity, _, _ = context
        try:
            job = _get_job(job_id)
            _ensure_owner(job, identity.user_id)
            _refresh_result_assets(job)
            if master_id not in {reference["id"] for reference in _master_references(job)}:
                raise JobNotFound("Master was not found.")
            approval = job_control.remote(
                JobOperation.APPROVE_MASTER.value,
                job_id,
                identity.user_id,
                master_id=master_id,
            )
            _raise_guard_error(approval)
            return public_job(_deserialize(dict(approval["job"])), _master_references(job))
        except DomainError as error:
            raise _api_error(error) from error

    @service.post("/v2/mascot/incubations/{job_id}/masters/{master_id}/select")
    async def select_incubator_master_v2(
        job_id: str,
        master_id: str,
        context: tuple[BffIdentity, str, str] = Depends(bff_operation_context),
    ):
        """Persist one owner selection for an ambiguous incubator ranking."""
        identity, _, _ = context
        try:
            job = _get_job(job_id)
            _ensure_owner(job, identity.user_id)
            _refresh_result_assets(job)
            if master_id not in {reference["id"] for reference in _master_references(job)}:
                raise JobNotFound("Master was not found.")
            selected = job_control.remote(
                JobOperation.SELECT_INCUBATOR_MASTER.value,
                job_id,
                identity.user_id,
                master_id=master_id,
            )
            _raise_guard_error(selected)
            advanced = advance_async_incubation.remote(job_id)
            _raise_guard_error(advanced)
            current = _deserialize(dict(advanced["job"]))
            return _public_job_with_assets(current)
        except DomainError as error:
            raise _api_error(error) from error

    @service.patch("/v2/mascot/jobs/{job_id}/configuration")
    async def update_mascot_configuration_v2(
        job_id: str,
        request: MascotConfigurationV2Request,
        context: tuple[BffIdentity, str, str] = Depends(bff_operation_context),
    ):
        identity, _, _ = context
        started_at = time.monotonic()
        try:
            job = _get_job(job_id)
            _ensure_owner(job, identity.user_id)
            structured_event(
                "configuration_update_started",
                environment=ENVIRONMENT.value,
                puleiroTraceId=_trace_id_for_record(job),
                attemptId=identity.attempt_id,
                jobId=job_id,
            )
            choices = validate_pose_choices(request.pose_choices) if request.pose_choices is not None else None
            updated = job_control.remote(
                JobOperation.UPDATE_CONFIGURATION.value,
                job_id,
                identity.user_id,
                pose_choices=choices,
                display_name=_normalized_display_name(request.display_name) if request.display_name is not None else None,
                configuration_revision=request.configuration_revision,
            )
            _raise_guard_error(updated)
            current = _deserialize(dict(updated["job"]))
            # The approved Master assets are immutable while the user edits
            # configuration. Reloading the shared Volume here made every name
            # or pose edit wait for storage synchronization. A cold API
            # container already mounts the latest committed Volume state; the
            # asset-serving endpoints retain their explicit reload safeguard.
            response = _public_job_with_assets(current)
            structured_event(
                "configuration_update_completed",
                environment=ENVIRONMENT.value,
                result="updated",
                durationMs=_elapsed_ms(started_at),
                puleiroTraceId=_trace_id_for_record(current),
                attemptId=identity.attempt_id,
                jobId=job_id,
            )
            return response
        except (DomainError, ValueError) as error:
            structured_event(
                "configuration_update_failed",
                environment=ENVIRONMENT.value,
                result="failed",
                durationMs=_elapsed_ms(started_at),
                attemptId=identity.attempt_id,
                jobId=job_id,
                safeErrorCode=getattr(error, "code", "INVALID_REQUEST"),
            )
            raise _api_error(error) from error

    @service.get("/v2/mascot/jobs/{job_id}/masters/{master_id}")
    async def download_master_v2(
        job_id: str,
        master_id: str,
        identity: BffIdentity = Depends(verified_bff_identity),
    ):
        from fastapi.responses import FileResponse
        try:
            job = _get_job(job_id)
            _ensure_owner(job, identity.user_id)
            _refresh_result_assets(job)
            if master_id not in {reference["id"] for reference in _master_references(job)}:
                raise JobNotFound("Master was not found.")
            path = _asset_path(job_id, "masters", f"{master_id}.png")
            if not path.is_file():
                raise JobNotFound("Master was not found.")
            return FileResponse(path, media_type="image/png", filename=f"{master_id}.png")
        except DomainError as error:
            raise _api_error(error) from error

    @service.get("/v2/mascot/jobs/{job_id}/poses/{role}")
    async def download_pose_v2(
        job_id: str,
        role: Literal["normal", "listening", "transcribing"],
        identity: BffIdentity = Depends(verified_bff_identity),
    ):
        from fastapi.responses import FileResponse
        try:
            job = _get_job(job_id)
            _ensure_owner(job, identity.user_id)
            _refresh_result_assets(job)
            pose = next((item for item in _pose_references(job) if item["role"] == role), None)
            if pose is None:
                raise JobNotFound("Pose was not found.")
            path = _asset_path(job_id, "poses", f"{pose['id']}.png")
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != pose["sha256"]:
                raise JobNotFound("Pose was not found.")
            return FileResponse(path, media_type="image/png", filename=f"{role}.png")
        except DomainError as error:
            raise _api_error(error) from error

    @service.post("/v2/mascot/jobs/{job_id}/pose-generations", status_code=202)
    async def start_pose_generation_v2(
        job_id: str,
        request: PoseGenerationV2Request,
        context: tuple[BffIdentity, str, str] = Depends(bff_operation_context),
    ):
        started_at = time.monotonic()
        identity, _, operation_id = context
        try:
            job = _get_job(job_id)
            _ensure_owner(job, identity.user_id)
            _reload_template_assets()
            _require_pose_generation_enabled()
            if not _templates_installed():
                raise GuardRejected("POSE_TEMPLATES_UNAVAILABLE", "Pose templates are not installed.")
            if request.catalog_version is not None and request.catalog_version != WEB_POSE_CATALOG_VERSION:
                raise GuardRejected("POSE_CATALOG_INCOMPATIBLE", "Pose catalog is not compatible with this service.")
            choices = validate_pose_choices(request.pose_choices)
            _refresh_result_assets(job)
            _verify_master_outputs(job)
            request_id = CURRENT_REQUEST_ID.get()
            correlation_id = _trace_id_for_record(job)
            operation_fingerprint = _pose_operation_fingerprint(identity, job, choices)
            structured_event(
                "pose_request_received",
                environment=ENVIRONMENT.value,
                puleiroTraceId=correlation_id,
                attemptId=identity.attempt_id,
                operationId=operation_id,
                requestId=request_id,
                jobId=job_id,
                masterId=job.master_id,
            )
            enqueued = job_control.remote(
                JobOperation.ENQUEUE_POSES.value,
                job_id,
                user_id=identity.user_id,
                pose_choices=choices,
                operation_id=operation_id,
                operation_fingerprint=operation_fingerprint,
                correlation_id=correlation_id,
                request_id=request_id,
            )
            _raise_guard_error(enqueued)
            response_job = dict(enqueued["job"])
            created = bool(enqueued["changed"])
            reserved = bool(enqueued["reserved"])
            structured_event(
                "pose_operation_created" if created else "pose_operation_replayed",
                environment=ENVIRONMENT.value,
                result="created" if created else "replayed",
                durationMs=_elapsed_ms(started_at),
                puleiroTraceId=correlation_id,
                attemptId=identity.attempt_id,
                operationId=str(response_job.get("pose_operation_id") or operation_id),
                requestId=request_id,
                jobId=job_id,
                masterId=job.master_id,
            )
            if reserved:
                _require_pose_generation_enabled()
                structured_event(
                    "pose_queue_reserved",
                    environment=ENVIRONMENT.value,
                    result="reserved",
                    puleiroTraceId=correlation_id,
                    attemptId=identity.attempt_id,
                    operationId=operation_id,
                    requestId=request_id,
                    jobId=job_id,
                    masterId=job.master_id,
                )
                observer = InferenceObserver(_trace_id_for_record(job))
                observer.event("pose_job_queued", {"outputs": 3, "gpu_type": MASTER_GPU})
                pose_call = _spawn_pose_worker(job_id)
                recorded = job_control.remote(
                    JobOperation.RECORD_POSE_GPU_CALL.value,
                    job_id,
                    call_id=pose_call.object_id,
                )
                _raise_guard_error(recorded)
                response_job = dict(recorded["job"])
                structured_event(
                    "pose_worker_spawned",
                    environment=ENVIRONMENT.value,
                    result="spawned",
                    puleiroTraceId=correlation_id,
                    attemptId=identity.attempt_id,
                    operationId=operation_id,
                    requestId=request_id,
                    jobId=job_id,
                    masterId=job.master_id,
                )
            response_operation_id = str(response_job.get("pose_operation_id") or operation_id)
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=202,
                content=public_job(_deserialize(response_job)) | {"idempotentReplay": not created},
                headers={"X-Operation-Id": response_operation_id},
            )
        except (DomainError, ValueError) as error:
            raise _api_error(error) from error

    @service.get("/v1/mascot/jobs/{job_id}")
    async def read_job(job_id: str, user_id: str = Depends(secure_user)):
        try:
            job = _get_job(job_id)
            _ensure_owner(job, user_id)
            if _should_reconcile_master(job):
                reconciled = job_control.remote(JobOperation.RECONCILE_MASTER.value, job_id)
                _raise_guard_error(reconciled)
                job = _deserialize(dict(reconciled["job"]))
            _refresh_result_assets(job)
            return _serialize(job)
        except DomainError as error:
            raise _api_error(error) from error

    @service.get("/v1/mascot/idempotency/{idempotency_key}")
    async def recover_job(idempotency_key: str, user_id: str = Depends(secure_user)):
        try:
            job_id = str(idempotency[_record_key(user_id, idempotency_key)])
            job = _get_job(job_id)
            _ensure_owner(job, user_id)
            _refresh_result_assets(job)
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
            _require_master_generation_enabled()
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
            _refresh_result_assets(job)
            operation_key = _operation_key(context[0], f"approve:{job_id}:{request.master_id}")
            if operation_key in idempotency:
                return _serialize(job)
            if not _asset_path(job_id, "masters", f"{request.master_id}.png").is_file():
                raise JobNotFound("Master was not found.")
            approval = job_control.remote(
                JobOperation.APPROVE_MASTER.value, job_id, context[0], master_id=request.master_id
            )
            _raise_guard_error(approval)
            approved_job = _deserialize(dict(approval["job"]))
            idempotency[operation_key] = job.job_id
            return _serialize(approved_job)
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

    @service.get("/v1/mascot/jobs/{job_id}/result")
    async def result(job_id: str, user_id: str = Depends(secure_user)):
        try:
            job = _get_job(job_id)
            _ensure_owner(job, user_id)
            if job.state is not JobState.COMPLETED:
                raise DomainError("Mascot result is not ready.")
            _refresh_result_assets(job)
            return _result_payload(job)
        except DomainError as error:
            raise _api_error(error) from error

    @service.get("/v1/mascot/jobs/{job_id}/masters/{master_id}")
    async def download_master(job_id: str, master_id: str, user_id: str = Depends(secure_user)):
        from fastapi.responses import FileResponse
        if master_id not in {f"master_{index}" for index in range(1, len(MASTER_SEEDS) + 1)}:
            raise _api_error(JobNotFound("Master was not found."))
        job = _get_job(job_id)
        _ensure_owner(job, user_id)
        _refresh_result_assets(job)
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

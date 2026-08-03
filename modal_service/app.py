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
from dataclasses import asdict
from pathlib import Path
import modal

from modal_service.catalog import POSE_PROMPT_VERSION
from modal_service.config import Environment, generation_enabled, limits_for
from modal_service.coordinator import JobCoordinator, JobOperation
from modal_service.costs import CostLimitExceeded, RateLimitExceeded
from modal_service.domain import DomainError, JobNotFound, JobRecord, JobState
from modal_service.security import AuthenticationRejected, app_check_token, bearer_token, may_schedule_gpu, valid_firebase_claims
from modal_service.validation import ImageValidationError, validate_image

APP_NAME = "gru-mascot"
FIREBASE_PROJECT_ID = "gru-mascote"
FIREBASE_PROJECT_NUMBER = "816774877835"
ASSET_ROOT = "/gru-assets"
MODEL_ROOT = "/gru-models"
ENVIRONMENT = Environment(os.getenv("GRU_MASCOT_ENV", Environment.DEVELOPMENT))
LIMITS = limits_for(ENVIRONMENT)
GPU_GENERATION_ENABLED = generation_enabled(ENVIRONMENT, os.getenv("GPU_GENERATION_ENABLED"))

api_image = modal.Image.debian_slim(python_version="3.12").pip_install(
    "fastapi[standard]>=0.115,<1", "pillow>=11,<12", "httpx>=0.28,<1", "google-auth>=2.38,<3", "firebase-admin>=6.6,<7"
)
gpu_image = api_image.pip_install(
    "torch>=2.6,<3", "diffusers>=0.35", "transformers>=4.51", "accelerate>=1.6", "safetensors>=0.5"
)
app = modal.App(APP_NAME)
assets = modal.Volume.from_name("gru-mascot-assets", create_if_missing=True)
models = modal.Volume.from_name("gru-mascot-models", create_if_missing=True)
jobs = modal.Dict.from_name("gru-mascot-jobs", create_if_missing=True)
idempotency = modal.Dict.from_name("gru-mascot-idempotency", create_if_missing=True)
usage = modal.Dict.from_name("gru-mascot-usage", create_if_missing=True)
firebase_admin_secret = modal.Secret.from_name("gru-mascot-firebase-admin")


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
    if job.state is JobState.AWAITING_MASTER_APPROVAL:
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
    return HTTPException(status_code=status, detail={"code": code, "message": str(error)})


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


@app.function(image=api_image, max_containers=1)
@modal.concurrent(max_inputs=1)
def register_job(user_id: str, idempotency_key: str, source_key: str) -> dict[str, object]:
    try:
        coordinator = JobCoordinator(jobs, idempotency, usage, LIMITS, utc_day_key())
        job, created = coordinator.register(user_id, idempotency_key, source_key)
        return {"job": _serialize(job), "created": created}
    except (DomainError, CostLimitExceeded, RateLimitExceeded) as error:
        return {"error_code": getattr(error, "code", "INVALID_REQUEST"), "error_message": str(error)}


@app.function(image=api_image, max_containers=1, volumes={ASSET_ROOT: assets})
@modal.concurrent(max_inputs=1)
def job_control(
    operation: str,
    job_id: str,
    user_id: str = "",
    master_id: str = "",
    call_id: str = "",
    outputs: list[bytes] | None = None,
) -> dict[str, object]:
    try:
        coordinator = JobCoordinator(jobs, idempotency, usage, LIMITS, utc_day_key())
        command = JobOperation(operation)
        changed = False
        if command is JobOperation.AUTHORIZE_GENERATION:
            changed = coordinator.authorize_generation(job_id, user_id, GPU_GENERATION_ENABLED)
            job = coordinator.get(job_id)
        elif command is JobOperation.START_MASTER:
            job, changed = coordinator.transition_if_active(job_id, JobState.VALIDATING_INPUT, JobState.GENERATING_MASTER)
        elif command is JobOperation.COMMIT_MASTER:
            job, changed = coordinator.commit_master_outputs(
                job_id, lambda current: _persist_master_outputs(current, outputs or [])
            )
        elif command is JobOperation.FAIL_MASTER:
            job, changed = coordinator.transition_if_active(
                job_id, JobState.GENERATING_MASTER, JobState.FAILED, "MASTER_GENERATION_FAILED"
            )
        elif command is JobOperation.RECORD_GPU_CALL:
            job, changed = coordinator.record_gpu_call(job_id, call_id)
        elif command is JobOperation.APPROVE_MASTER:
            job, changed = coordinator.approve_master(job_id, user_id, master_id, POSE_PROMPT_VERSION)
        elif command is JobOperation.CANCEL:
            job, changed = coordinator.cancel(job_id, user_id)
        else:  # StrEnum exhaustiveness guard.
            raise DomainError("Unsupported job operation.")
        return {"job": _serialize(job), "changed": changed}
    except (DomainError, CostLimitExceeded, RateLimitExceeded) as error:
        return {"error_code": getattr(error, "code", "INVALID_REQUEST"), "error_message": str(error)}


@app.function(
    image=gpu_image,
    gpu="L40S",
    timeout=LIMITS.model_timeout_seconds,
    min_containers=0,
    max_containers=LIMITS.max_containers,
    scaledown_window=30,
    volumes={ASSET_ROOT: assets, MODEL_ROOT: models},
)
def generate_master(job_id: str) -> None:
    """GPU boundary. The Qwen provider is enabled only after a smoke fixture exists."""
    if not GPU_GENERATION_ENABLED:
        logging.warning("generation_blocked job_id=%s", job_id)
        return
    started = job_control.remote(JobOperation.START_MASTER.value, job_id)
    _raise_guard_error(started)
    if not bool(started["changed"]):
        return
    job = _deserialize(dict(started["job"]))
    try:
        outputs = _generate_qwen_masters(job)
        committed = job_control.remote(JobOperation.COMMIT_MASTER.value, job_id, outputs=outputs)
        _raise_guard_error(committed)
    except Exception as error:  # GPU libraries expose unstable exception classes.
        logging.exception("master_generation_failed job_id=%s", job.job_id)
        failed = job_control.remote(JobOperation.FAIL_MASTER.value, job_id)
        _raise_guard_error(failed)
        if bool(failed["changed"]):
            raise error


def _generate_qwen_masters(job: JobRecord) -> list[bytes]:
    """Load Qwen lazily; model bytes live on a persistent Modal Volume."""
    from io import BytesIO

    import torch
    from diffusers import QwenImageEditPlusPipeline
    from PIL import Image

    source = Image.open(_asset_path(job.job_id, "original", "source.bin")).convert("RGB")
    pipeline = QwenImageEditPlusPipeline.from_pretrained(
        "Qwen/Qwen-Image-Edit-2511", torch_dtype=torch.bfloat16, cache_dir=MODEL_ROOT
    ).to("cuda")
    models.commit()
    outputs: list[bytes] = []
    for seed in range(3):
        generated = pipeline(image=[source], prompt=_master_prompt(), generator=torch.Generator("cuda").manual_seed(seed), num_inference_steps=40).images[0]
        buffer = BytesIO()
        generated.save(buffer, format="PNG")
        outputs.append(buffer.getvalue())
    return outputs


def _master_prompt() -> str:
    from modal_service.catalog import MASTER_PROMPT

    return MASTER_PROMPT


def _persist_master_outputs(job: JobRecord, outputs: list[bytes]) -> None:
    if not outputs:
        raise DomainError("Master generation returned no images.")
    staging = Path(ASSET_ROOT, "temporary", job.job_id, "masters")
    target = Path(ASSET_ROOT, "masters", job.job_id)
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True, exist_ok=True)
    for index, content in enumerate(outputs, start=1):
        destination = staging / f"master_{index}.png"
        destination.write_bytes(content)
    shutil.rmtree(target, ignore_errors=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    staging.replace(target)
    assets.commit()


@app.function(image=api_image, volumes={ASSET_ROOT: assets}, secrets=[firebase_admin_secret], max_containers=1)
@modal.asgi_app()
def api():
    from fastapi import Depends, FastAPI, Header
    import firebase_admin
    from firebase_admin import app_check as firebase_app_check
    from firebase_admin import credentials
    from google.auth.transport.requests import Request as GoogleRequest
    from google.oauth2 import id_token
    from pydantic import BaseModel, Field

    service = FastAPI(title="GRU Mascot API", docs_url=None, redoc_url=None)
    credentials_json = os.environ.get("FIREBASE_ADMIN_CREDENTIALS_JSON")
    if not credentials_json:
        raise RuntimeError("Firebase Admin credentials are required for protected API startup.")
    try:
        firebase_admin.get_app()
    except ValueError:
        firebase_admin.initialize_app(credentials.Certificate(json.loads(credentials_json)))

    class CreateJobRequest(BaseModel):
        image_base64: str = Field(min_length=1, max_length=14_000_000)
        content_type: str | None = None

    class ApproveMasterRequest(BaseModel):
        master_id: str = Field(pattern=r"^master_[1-4]$")

    class PoseRequest(BaseModel):
        pose_id: str = Field(pattern=r"^pose_[0-9]{2}$")

    # These dependencies live inside the ASGI factory. Keep FastAPI markers in
    # defaults so postponed annotations cannot turn them into public query args.
    async def verified_user(authorization: str | None = Header(default=None)) -> str:
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

    @service.get("/health")
    async def health() -> dict[str, object]:
        return {
            "service": APP_NAME,
            "environment": ENVIRONMENT.value,
            "generation_enabled": GPU_GENERATION_ENABLED,
            "templates_installed": _templates_installed(),
            "model_configured": True,
        }

    @service.post("/v1/mascot/jobs", status_code=202)
    async def create_job(request: CreateJobRequest, context: tuple[str, str] = Depends(cost_context)):
        user_id, key = context
        try:
            content = _decode_image(request.image_base64)
            _, _, _ = validate_image(content, request.content_type)
            digest = hashlib.sha256(content).hexdigest()
            registration = register_job.remote(user_id, key, f"original/{digest}")
            _raise_guard_error(registration)
            job_data = dict(registration["job"])
            destination = _asset_path(str(job_data["job_id"]), "original", "source.bin")
            if not destination.is_file() or hashlib.sha256(destination.read_bytes()).hexdigest() != digest:
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(content)
                assets.commit()
            authorization = job_control.remote(JobOperation.AUTHORIZE_GENERATION.value, str(job_data["job_id"]), user_id)
            _raise_guard_error(authorization)
            if may_schedule_gpu(GPU_GENERATION_ENABLED, bool(authorization["changed"])):
                function_call = generate_master.spawn(str(job_data["job_id"]))
                recorded = job_control.remote(
                    JobOperation.RECORD_GPU_CALL.value,
                    str(job_data["job_id"]),
                    call_id=function_call.object_id,
                )
                _raise_guard_error(recorded)
                job_data = dict(recorded["job"])
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
            job_id = str(idempotency[_record_key(user_id, idempotency_key)])
            job = _get_job(job_id)
            _ensure_owner(job, user_id)
            return _serialize(job)
        except KeyError as error:
            raise _api_error(JobNotFound("Job was not found.")) from error
        except DomainError as error:
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

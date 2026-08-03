"""Modal deployment entrypoint for the GRU Mascot service.

Firebase Authentication authenticates every cost-bearing request. The Android
client never receives a Modal account or proxy credential.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import os
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Annotated

import modal

from modal_service.catalog import MASTER_PROMPT_VERSION, POSE_PROMPT_VERSION, POSE_TEMPLATE_VERSION
from modal_service.config import Environment, limits_for
from modal_service.domain import DomainError, JobRecord, JobState
from modal_service.validation import ImageValidationError, validate_image

APP_NAME = "gru-mascot"
ASSET_ROOT = "/gru-assets"
MODEL_ROOT = "/gru-models"
ENVIRONMENT = Environment(os.getenv("GRU_MASCOT_ENV", Environment.DEVELOPMENT))
LIMITS = limits_for(ENVIRONMENT)

api_image = modal.Image.debian_slim(python_version="3.12").pip_install(
    "fastapi[standard]>=0.115,<1", "pillow>=11,<12", "httpx>=0.28,<1", "google-auth>=2.38,<3"
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


def _record_key(user_id: str, idempotency_key: str) -> str:
    return f"{user_id}:{idempotency_key}"


def _asset_path(job_id: str, folder: str, name: str) -> Path:
    return Path(ASSET_ROOT, folder, job_id, name)


def _decode_image(value: str) -> bytes:
    try:
        return base64.b64decode(value, validate=True)
    except ValueError as error:
        raise ImageValidationError("Image is not valid base64.") from error


def _serialize(job: JobRecord) -> dict[str, object]:
    payload = asdict(job) | {"state": job.state.value}
    if job.state is JobState.AWAITING_MASTER_APPROVAL:
        payload["masters"] = {f"master_{index}": {"id": f"master_{index}"} for index in range(1, 4)}
    return payload


def _deserialize(record: dict[str, object]) -> JobRecord:
    return JobRecord(**(record | {"state": JobState(record["state"])}))


def _get_job(job_id: str) -> JobRecord:
    try:
        return _deserialize(jobs[job_id])
    except KeyError as error:
        raise DomainError("Job was not found.") from error


def _save_job(job: JobRecord) -> None:
    jobs[job.job_id] = _serialize(job)


def _ensure_owner(job: JobRecord, user_id: str) -> None:
    if job.user_id != user_id:
        raise DomainError("Job was not found.")


def _api_error(error: Exception):
    from fastapi import HTTPException

    code = getattr(error, "code", "INVALID_REQUEST")
    status = 400 if code in {"INVALID_IMAGE", "INVALID_REQUEST"} else 409
    return HTTPException(status_code=status, detail={"code": code, "message": str(error)})


def _request_context(user_id: str, idempotency_key: str) -> tuple[str, str]:
    if not user_id.strip() or not idempotency_key.strip():
        raise DomainError("Verified user identity and idempotency key are required.")
    return user_id.strip(), idempotency_key.strip()


def _new_job(user_id: str, idempotency_key: str, source_key: str) -> JobRecord:
    return JobRecord(
        job_id=f"job_{uuid.uuid4().hex}",
        user_id=user_id,
        idempotency_key=idempotency_key,
        source_key=source_key,
        model_version="Qwen-Image-Edit-2511",
        prompt_version=MASTER_PROMPT_VERSION,
        template_version=POSE_TEMPLATE_VERSION,
    )


def _transition(job: JobRecord, state: JobState) -> None:
    job.transition_to(state)
    _save_job(job)


def _reserve_budget() -> None:
    """Development guard; one API container serializes reservations in this phase."""
    day_key = utc_day_key()
    try:
        current = float(usage[day_key])
    except KeyError:
        current = 0.0
    next_total = current + LIMITS.estimated_generation_cost_usd
    if next_total > LIMITS.daily_cost_cap_usd:
        from modal_service.costs import CostLimitExceeded

        raise CostLimitExceeded("Daily generation cost cap reached.")
    usage[day_key] = round(next_total, 4)


def utc_day_key() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).date().isoformat()


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
    job = _get_job(job_id)
    if job.state is not JobState.VALIDATING_INPUT:
        return
    _transition(job, JobState.GENERATING_MASTER)
    try:
        outputs = _generate_qwen_masters(job)
        _persist_master_outputs(job, outputs)
        _transition(job, JobState.AWAITING_MASTER_APPROVAL)
    except Exception as error:  # GPU libraries expose unstable exception classes.
        logging.exception("master_generation_failed job_id=%s", job.job_id)
        job.error_code = "MASTER_GENERATION_FAILED"
        _transition(job, JobState.FAILED)
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
    for index, content in enumerate(outputs, start=1):
        destination = _asset_path(job.job_id, "masters", f"master_{index}.png")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
    assets.commit()


@app.function(image=api_image, volumes={ASSET_ROOT: assets}, max_containers=1)
@modal.asgi_app()
def api():
    from fastapi import Depends, FastAPI, Header
    from google.auth.transport.requests import Request as GoogleRequest
    from google.oauth2 import id_token
    from pydantic import BaseModel, Field

    service = FastAPI(title="GRU Mascot API", docs_url=None, redoc_url=None)

    class CreateJobRequest(BaseModel):
        image_base64: str = Field(min_length=1, max_length=14_000_000)
        content_type: str | None = None

    class ApproveMasterRequest(BaseModel):
        master_id: str = Field(pattern=r"^master_[1-4]$")

    class PoseRequest(BaseModel):
        pose_id: str = Field(pattern=r"^pose_[0-9]{2}$")

    async def verified_user(authorization: Annotated[str | None, Header()] = None) -> str:
        if not authorization or not authorization.startswith("Bearer "):
            from fastapi import HTTPException
            raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "A valid identity is required."})
        try:
            claims = id_token.verify_firebase_token(authorization.removeprefix("Bearer "), GoogleRequest(), audience="gru-mascote")
            if claims.get("iss") != "https://securetoken.google.com/gru-mascote" or not claims.get("uid"):
                raise ValueError("Unexpected Firebase token claims.")
            return str(claims["uid"])
        except Exception as error:
            logging.info("firebase_token_rejected type=%s", type(error).__name__)
            from fastapi import HTTPException
            raise HTTPException(status_code=401, detail={"code": "UNAUTHENTICATED", "message": "A valid identity is required."}) from error

    async def cost_context(
        user_id: Annotated[str, Depends(verified_user)], x_idempotency_key: Annotated[str | None, Header()] = None,
    ) -> tuple[str, str]:
        return _request_context(user_id, x_idempotency_key or "")

    @service.get("/health")
    async def health() -> dict[str, object]:
        return {"service": APP_NAME, "environment": ENVIRONMENT.value, "gpu_enabled": True}

    @service.post("/v1/mascot/jobs", status_code=202)
    async def create_job(request: CreateJobRequest, context: Annotated[tuple[str, str], Depends(cost_context)]):
        user_id, key = context
        request_key = _record_key(user_id, key)
        if request_key in idempotency:
            return {"job_id": idempotency[request_key], "idempotent_replay": True}
        try:
            content = _decode_image(request.image_base64)
            _, _, _ = validate_image(content, request.content_type)
            digest = hashlib.sha256(content).hexdigest()
            job = _new_job(user_id, key, f"original/{digest}")
            _reserve_budget()
            destination = _asset_path(job.job_id, "original", "source.bin")
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)
            assets.commit()
            _transition(job, JobState.VALIDATING_INPUT)
            idempotency[request_key] = job.job_id
            generate_master.spawn(job.job_id)
            return {"job_id": job.job_id, "state": job.state.value, "idempotent_replay": False}
        except (ImageValidationError, DomainError) as error:
            raise _api_error(error) from error

    @service.get("/v1/mascot/jobs/{job_id}")
    async def read_job(job_id: str, user_id: Annotated[str, Depends(verified_user)]):
        try:
            job = _get_job(job_id)
            _ensure_owner(job, user_id)
            return _serialize(job)
        except DomainError as error:
            raise _api_error(error) from error

    @service.post("/v1/mascot/jobs/{job_id}/approve-master", status_code=202)
    async def approve_master(job_id: str, request: ApproveMasterRequest, context: Annotated[tuple[str, str], Depends(cost_context)]):
        try:
            job = _get_job(job_id)
            _ensure_owner(job, context[0])
            if job.state is JobState.AWAITING_MASTER_APPROVAL and job.master_id == request.master_id:
                return _serialize(job)
            if job.state is not JobState.AWAITING_MASTER_APPROVAL:
                raise DomainError("Master approval is not available for this job.")
            job.master_id = request.master_id
            job.prompt_version = POSE_PROMPT_VERSION
            _transition(job, JobState.CONSISTENCY_TEST)
            return _serialize(job)
        except DomainError as error:
            raise _api_error(error) from error

    @service.post("/v1/mascot/jobs/{job_id}/cancel")
    async def cancel_job(job_id: str, context: Annotated[tuple[str, str], Depends(cost_context)]):
        try:
            job = _get_job(job_id)
            _ensure_owner(job, context[0])
            if job.state not in {JobState.COMPLETED, JobState.FAILED, JobState.CANCELED}:
                _transition(job, JobState.CANCELED)
            return _serialize(job)
        except DomainError as error:
            raise _api_error(error) from error

    @service.get("/v1/mascot/jobs/{job_id}/result")
    async def result(job_id: str, user_id: Annotated[str, Depends(verified_user)]):
        try:
            job = _get_job(job_id)
            _ensure_owner(job, user_id)
            if job.state is not JobState.COMPLETED:
                raise DomainError("Mascot result is not ready.")
            return _serialize(job) | {"poses": []}
        except DomainError as error:
            raise _api_error(error) from error

    @service.post("/v1/mascot/jobs/{job_id}/consistency", status_code=202)
    async def run_consistency(job_id: str, context: Annotated[tuple[str, str], Depends(cost_context)]):
        return _template_assets_required(job_id, context[0])

    @service.post("/v1/mascot/jobs/{job_id}/generate-poses", status_code=202)
    async def generate_poses(job_id: str, context: Annotated[tuple[str, str], Depends(cost_context)]):
        return _template_assets_required(job_id, context[0])

    @service.post("/v1/mascot/jobs/{job_id}/retry-pose", status_code=202)
    async def retry_pose(job_id: str, request: PoseRequest, context: Annotated[tuple[str, str], Depends(cost_context)]):
        del request
        return _template_assets_required(job_id, context[0])

    def _template_assets_required(job_id: str, user_id: str):
        from fastapi import HTTPException
        try:
            job = _get_job(job_id)
            _ensure_owner(job, user_id)
        except DomainError as error:
            raise _api_error(error) from error
        raise HTTPException(
            status_code=409,
            detail={"code": "TEMPLATE_ASSETS_UNAVAILABLE", "message": "Official pose templates are not installed."},
        )

    return service

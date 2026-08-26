"""Private BFF-facing Modal v2 routes.

The Android client remains on ``/v1/mascot`` with Firebase/App Check.  These
routes are deliberately installed separately and accept only a short-lived
JWT minted by the Puleiro BFF.  The JWT is an authentication boundary, not a
replacement for per-job ownership and attempt checks below.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, Field


_ATTEMPT_PATTERN = re.compile(r"^[0-9a-f]{8}-[0-9a-f-]{27,36}$", re.IGNORECASE)
_OPERATION_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{8,160}$")
_POSE_ROLES = frozenset({"normal", "listening", "transcribing"})


class WebV2SubjectIdentity(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    category: str = Field(pattern=r"^[a-z_]{2,32}$")
    label: str = Field(min_length=1, max_length=80)
    species: str | None = Field(default=None, max_length=80)
    confirmed: bool


class WebV2CreateJobRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    image_base64: str = Field(min_length=1, max_length=14_000_000)
    content_type: str | None = Field(default=None, max_length=100)
    attempt_id: str = Field(pattern=r"^[0-9a-fA-F-]{32,36}$")
    subject_identity: WebV2SubjectIdentity


class WebV2PoseGenerationRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    pose_choices: dict[str, str]
    catalog_version: str = Field(min_length=1, max_length=64)


@dataclass(frozen=True)
class WebV2Dependencies:
    """Narrow bridge to the legacy Modal module; avoids changing Android V1."""

    get_job: Callable[[str], Any]
    ensure_owner: Callable[[Any, str], None]
    api_error: Callable[[Exception], Exception]
    asset_path: Callable[[str, str, str], Path]
    decode_image: Callable[[str], bytes]
    validate_image: Callable[..., Any]
    strip_metadata: Callable[[bytes], bytes]
    register_job: Callable[..., dict[str, object]]
    schedule_master: Callable[[str, str], dict[str, object]]
    approve_master: Callable[..., dict[str, object]]
    schedule_poses: Callable[[str, str, dict[str, str], str, str], dict[str, object]]
    capabilities: Callable[[], dict[str, object]]
    templates_installed: Callable[[], bool]
    generation_enabled: bool
    max_body_bytes: int
    assets: Any
    operations: Any
    environment: str
    app_name: str


def prepare_web_v2_upload(
    image_base64: str,
    declared_content_type: str | None,
    decode_image: Callable[[str], bytes],
    validate_image: Callable[..., Any],
    strip_metadata: Callable[[bytes], bytes],
) -> bytes:
    """Validate the original upload, then return its privacy-scrubbed bytes."""
    source = decode_image(image_base64)
    validate_image(source, declared_content_type)
    sanitized = strip_metadata(source)
    validate_image(sanitized)
    return sanitized


def install_web_v2_routes(service: Any, dependencies: WebV2Dependencies, jwt_secret: str | None) -> None:
    """Install V2 on an existing FastAPI application.

    ``jwt_secret`` is intentionally passed from the API factory so it never
    becomes an import-time value or a client-visible configuration.
    """
    from fastapi import Header, HTTPException, Request
    from fastapi.responses import FileResponse, JSONResponse
    class WebV2Error(ValueError):
        def __init__(self, code: str, message: str, status: int = 400, retryable: bool = False) -> None:
            super().__init__(message)
            self.code = code
            self.status = status
            self.retryable = retryable

    def error_response(error: WebV2Error) -> HTTPException:
        return HTTPException(
            status_code=error.status,
            detail={"code": error.code, "message": str(error), "retryable": error.retryable},
        )

    def disabled_error() -> HTTPException:
        return error_response(WebV2Error("WEB_V2_DISABLED", "The Puleiro integration is not enabled.", 503, True))

    def read_claims(authorization: str | None) -> dict[str, Any]:
        if not jwt_secret:
            raise disabled_error()
        try:
            import jwt

            token = _bearer(authorization)
            claims = jwt.decode(
                token,
                jwt_secret,
                algorithms=["HS256"],
                audience=_env("MODAL_BFF_JWT_AUDIENCE", "gru-modal"),
                issuer=_env("MODAL_BFF_JWT_ISSUER", "puleiro-bff"),
                options={"require": ["exp", "iat", "sub", "attempt_id"]},
            )
        except Exception as error:
            raise error_response(WebV2Error("BFF_TOKEN_INVALID", "A valid Puleiro service identity is required.", 401)) from error
        owner_id = claims.get("sub")
        attempt_id = claims.get("attempt_id")
        if not isinstance(owner_id, str) or not owner_id or not isinstance(attempt_id, str) or not _ATTEMPT_PATTERN.fullmatch(attempt_id):
            raise error_response(WebV2Error("BFF_TOKEN_INVALID", "A valid Puleiro service identity is required.", 401))
        return {"owner_id": owner_id, "attempt_id": attempt_id}

    def request_context(
        authorization: str | None,
        correlation_id: str | None,
        operation_id: str | None,
        idempotency_key: str | None = None,
    ) -> dict[str, str]:
        claims = read_claims(authorization)
        if not correlation_id or not correlation_id.startswith("puleiro_") or len(correlation_id) > 160:
            raise error_response(WebV2Error("CORRELATION_ID_REQUIRED", "A valid correlation id is required."))
        if operation_id and not _OPERATION_PATTERN.fullmatch(operation_id):
            raise error_response(WebV2Error("OPERATION_ID_INVALID", "The operation id is invalid."))
        if idempotency_key and not _OPERATION_PATTERN.fullmatch(idempotency_key):
            raise error_response(WebV2Error("IDEMPOTENCY_KEY_INVALID", "The idempotency key is invalid."))
        return {
            "owner_id": claims["owner_id"],
            "attempt_id": claims["attempt_id"],
            "correlation_id": correlation_id,
            "operation_id": operation_id or "",
            "idempotency_key": idempotency_key or "",
        }

    def context_key(owner_id: str, attempt_id: str) -> str:
        digest = hashlib.sha256(f"{owner_id}\0{attempt_id}".encode()).hexdigest()
        return f"web-v2-attempt:{digest}"

    def job_context_key(job_id: str) -> str:
        return f"web-v2-job:{job_id}"

    def load_context(job_id: str, context: dict[str, str]) -> dict[str, Any]:
        stored = dependencies.operations.get(job_context_key(job_id))
        if not isinstance(stored, dict):
            raise error_response(WebV2Error("ATTEMPT_MISMATCH", "This attempt does not belong to the current session.", 404))
        if stored.get("owner_id") != context["owner_id"] or stored.get("attempt_id") != context["attempt_id"]:
            raise error_response(WebV2Error("ATTEMPT_MISMATCH", "This attempt does not belong to the current session.", 404))
        return dict(stored)

    def load_job(job_id: str, context: dict[str, str]) -> tuple[Any, dict[str, Any]]:
        stored = load_context(job_id, context)
        try:
            job = dependencies.get_job(job_id)
            dependencies.ensure_owner(job, context["owner_id"])
            return job, stored
        except Exception as error:
            raise dependencies.api_error(error) from error

    def v2_status(state: str) -> str:
        return {
            "QUEUED": "queued",
            "VALIDATING_INPUT": "queued",
            "READY_FOR_GENERATION": "registered",
            "GENERATING_MASTER": "generating_masters",
            "VALIDATING_MASTERS": "validating_masters",
            "AWAITING_MASTER_APPROVAL": "awaiting_master_approval",
            "VALIDATING_MASTER": "validating_master",
            "CONSISTENCY_TEST": "validating_master",
            "READY_FOR_POSES": "master_approved",
            "GENERATING_POSES": "generating_poses",
            "VALIDATING_POSES": "validating_poses",
            "AWAITING_SET_APPROVAL": "awaiting_set_approval",
            "PACKAGING": "packaging",
            "COMPLETED": "ready",
            "FAILED": "failed",
            "RECOVERY_REQUIRED": "failed",
            "CANCELED": "canceled",
        }.get(state, "failed")

    def serialize(job: Any, context: dict[str, str], stored: dict[str, Any], replay: bool = False) -> dict[str, Any]:
        def read_checks(folder: str) -> dict[str, dict[str, Any]]:
            path = dependencies.asset_path(job.job_id, folder, "checks.json")
            try:
                values = json.loads(path.read_text(encoding="utf-8")).get("checks", []) if path.is_file() else []
                return {str(item.get("assetId")): item for item in values if isinstance(item, dict)}
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                return {}

        master_checks = read_checks("masters")
        pose_checks = read_checks("poses")
        master_ids: list[str] = []
        for index in range(1, 4):
            candidate = f"master_{index}"
            if dependencies.asset_path(job.job_id, "masters", f"{candidate}.png").is_file():
                master_ids.append(candidate)
        poses: list[dict[str, str]] = []
        manifest = dependencies.asset_path(job.job_id, "poses", "manifest.json")
        if manifest.is_file():
            try:
                for pose in json.loads(manifest.read_text(encoding="utf-8")).get("poses", []):
                    role = str(pose.get("role", ""))
                    if role in _POSE_ROLES:
                        poses.append({
                            "id": str(pose.get("poseId", "")), "role": role,
                            "optionId": str(pose.get("optionId", "")), "label": role,
                            "sha256": str(pose.get("sha256", "")), "size": int(pose.get("size", 0)),
                            "templateVersion": str(pose.get("templateVersion", "")),
                            "qc": pose_checks.get(role),
                        })
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                pass
        error = None
        if getattr(job, "error_code", None):
            error = {"code": str(job.error_code), "retryable": str(job.state) == "RECOVERY_REQUIRED"}
        return {
            "jobId": job.job_id,
            "attemptId": context["attempt_id"],
            "status": v2_status(str(job.state)),
            "generationScheduled": str(job.state) not in {"READY_FOR_GENERATION", "CANCELED", "FAILED", "RECOVERY_REQUIRED"},
            "masters": [{"id": master_id, "qc": master_checks.get(master_id)} for master_id in master_ids],
            "approvedMasterId": getattr(job, "master_id", None),
            "subjectIdentity": stored.get("subject_identity"),
            "poseChoices": stored.get("pose_choices"),
            "poses": poses,
            "error": error,
            "operationId": context.get("operation_id") or stored.get("operation_id") or None,
            "idempotentReplay": replay,
        }

    def remember_operation(job_id: str, context: dict[str, str], action: str) -> bool:
        key = context.get("idempotency_key")
        if not key:
            return False
        operation_key = f"web-v2-operation:{action}:{context['owner_id']}:{job_id}:{key}"
        if dependencies.operations.get(operation_key):
            return True
        dependencies.operations[operation_key] = {"correlation_id": context["correlation_id"]}
        return False

    @service.get("/v2/mascot/health/live")
    async def web_v2_live() -> dict[str, object]:
        return {"service": dependencies.app_name, "contract": "v2", "status": "live", "environment": dependencies.environment}

    @service.get("/v2/mascot/health/ready")
    async def web_v2_ready():
        enabled = bool(jwt_secret)
        payload = {
            "service": dependencies.app_name,
            "contract": "v2",
            "status": "ready" if enabled else "not_ready",
            "generation_enabled": dependencies.generation_enabled,
            "dependencies": {"bff_jwt": "healthy" if enabled else "unhealthy", "jobs": "healthy", "assets": "healthy"},
        }
        return JSONResponse(status_code=200 if enabled else 503, content=payload)

    @service.get("/v2/mascot/health/generation")
    async def web_v2_generation():
        capability = dependencies.capabilities()
        ready = bool(jwt_secret) and bool(capability["master"]["ready"])
        return JSONResponse(
            status_code=200 if ready else 503,
            content={"service": dependencies.app_name, "contract": "v2", "status": "ready" if ready else "not_ready", "capabilities": capability},
        )

    @service.get("/v2/mascot/capabilities")
    async def web_v2_capabilities(
        authorization: str | None = Header(default=None),
        x_correlation_id: str | None = Header(default=None),
    ):
        request_context(authorization, x_correlation_id, None)
        return dependencies.capabilities()

    @service.post("/v2/mascot/jobs", status_code=202)
    async def web_create_job(
        request: WebV2CreateJobRequest,
        authorization: str | None = Header(default=None),
        x_correlation_id: str | None = Header(default=None),
        x_operation_id: str | None = Header(default=None),
        x_idempotency_key: str | None = Header(default=None),
    ):
        context = request_context(authorization, x_correlation_id, x_operation_id, x_idempotency_key)
        if request.attempt_id != context["attempt_id"]:
            raise error_response(WebV2Error("ATTEMPT_MISMATCH", "This attempt does not belong to the current session.", 403))
        if not context["idempotency_key"]:
            raise error_response(WebV2Error("IDEMPOTENCY_KEY_REQUIRED", "An idempotency key is required."))
        existing_id = dependencies.operations.get(context_key(context["owner_id"], context["attempt_id"]))
        if existing_id:
            job, stored = load_job(str(existing_id), context)
            return serialize(job, context, stored, replay=True)
        try:
            # The privacy scrub intentionally re-encodes to PNG. MIME matching
            # therefore belongs only to the original browser upload.
            content = prepare_web_v2_upload(
                request.image_base64,
                request.content_type,
                dependencies.decode_image,
                dependencies.validate_image,
                dependencies.strip_metadata,
            )
        except Exception as error:
            raise error_response(WebV2Error("INVALID_IMAGE", "The image could not be validated.")) from error
        digest = hashlib.sha256(content).hexdigest()
        registration = dependencies.register_job(
            context["owner_id"], context["idempotency_key"], f"original/{digest}",
            "image-processing-v1", request.subject_identity.model_dump(),
        )
        if registration.get("error_code"):
            code = str(registration["error_code"])
            raise error_response(WebV2Error(code, "The birth could not be registered.", 429 if code in {"RATE_LIMITED", "COST_LIMIT_REACHED"} else 409, code in {"RATE_LIMITED", "COST_LIMIT_REACHED"}))
        raw = dict(registration["job"])
        job_id = str(raw["job_id"])
        destination = dependencies.asset_path(job_id, "original", "source.bin")
        if not destination.is_file() or hashlib.sha256(destination.read_bytes()).hexdigest() != digest:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)
            dependencies.assets.commit()
        stored = {
            "owner_id": context["owner_id"],
            "attempt_id": context["attempt_id"],
            "subject_identity": request.subject_identity.model_dump(),
            "pose_choices": {"normal": "normal_attentive", "listening": "listening_focus", "transcribing": "transcribing_fast"},
            "correlation_id": context["correlation_id"],
            "operation_id": context["operation_id"],
        }
        dependencies.operations[context_key(context["owner_id"], context["attempt_id"])] = job_id
        dependencies.operations[job_context_key(job_id)] = stored
        job, stored = load_job(job_id, context)
        return serialize(job, context, stored, replay=not bool(registration.get("created", True)))

    @service.get("/v2/mascot/jobs")
    async def web_job_by_attempt(
        attempt_id: str,
        authorization: str | None = Header(default=None),
        x_correlation_id: str | None = Header(default=None),
        x_operation_id: str | None = Header(default=None),
    ):
        context = request_context(authorization, x_correlation_id, x_operation_id)
        if attempt_id != context["attempt_id"]:
            raise error_response(WebV2Error("ATTEMPT_MISMATCH", "This attempt does not belong to the current session.", 403))
        job_id = dependencies.operations.get(context_key(context["owner_id"], context["attempt_id"]))
        if not job_id:
            raise HTTPException(status_code=404, detail={"code": "JOB_NOT_FOUND", "message": "Birth not found."})
        job, stored = load_job(str(job_id), context)
        return serialize(job, context, stored)

    @service.get("/v2/mascot/jobs/{job_id}")
    async def web_read_job(
        job_id: str,
        authorization: str | None = Header(default=None),
        x_correlation_id: str | None = Header(default=None),
        x_operation_id: str | None = Header(default=None),
    ):
        context = request_context(authorization, x_correlation_id, x_operation_id)
        job, stored = load_job(job_id, context)
        return serialize(job, context, stored)

    @service.post("/v2/mascot/jobs/{job_id}/master-generations", status_code=202)
    async def web_start_masters(
        job_id: str,
        authorization: str | None = Header(default=None),
        x_correlation_id: str | None = Header(default=None),
        x_operation_id: str | None = Header(default=None),
        x_idempotency_key: str | None = Header(default=None),
    ):
        context = request_context(authorization, x_correlation_id, x_operation_id, x_idempotency_key)
        job, stored = load_job(job_id, context)
        # The same idempotency key may resume a classified worker failure. It
        # never creates a second job or a new reservation.
        resume_pending = (
            str(job.state) in {"RECOVERY_REQUIRED", "FAILED", "VALIDATING_INPUT"}
            and bool(job.generation_reserved)
        )
        if not resume_pending and remember_operation(job_id, context, "masters"):
            return serialize(job, context, stored, replay=True)
        if not dependencies.generation_enabled:
            raise error_response(WebV2Error("GENERATION_DISABLED", "GPU generation is disabled.", 409))
        try:
            scheduled = dependencies.schedule_master(job_id, context["owner_id"])
            if scheduled.get("error_code"):
                code = str(scheduled["error_code"])
                status = 429 if code in {"RATE_LIMITED", "COST_LIMIT_REACHED"} else 503
                raise WebV2Error(code, "The generation could not be scheduled.", status, True)
            job, stored = load_job(job_id, context)
            return serialize(job, context, stored)
        except WebV2Error as error:
            raise error_response(error) from error

    @service.post("/v2/mascot/jobs/{job_id}/masters/{master_id}/approve", status_code=202)
    async def web_approve_master(
        job_id: str,
        master_id: str,
        authorization: str | None = Header(default=None),
        x_correlation_id: str | None = Header(default=None),
        x_operation_id: str | None = Header(default=None),
        x_idempotency_key: str | None = Header(default=None),
    ):
        context = request_context(authorization, x_correlation_id, x_operation_id, x_idempotency_key)
        job, stored = load_job(job_id, context)
        if master_id not in {"master_1", "master_2", "master_3"} or not dependencies.asset_path(job_id, "masters", f"{master_id}.png").is_file():
            raise HTTPException(status_code=404, detail={"code": "MASTER_NOT_FOUND", "message": "Master not found."})
        if remember_operation(job_id, context, f"approve:{master_id}"):
            return serialize(job, context, stored, replay=True)
        approval = dependencies.approve_master(job_id, context["owner_id"], master_id)
        if approval.get("error_code"):
            raise error_response(WebV2Error(str(approval["error_code"]), "The master could not be approved.", 409))
        job, stored = load_job(job_id, context)
        return serialize(job, context, stored)

    @service.post("/v2/mascot/jobs/{job_id}/pose-generations", status_code=202)
    async def web_start_poses(
        job_id: str,
        request: WebV2PoseGenerationRequest,
        authorization: str | None = Header(default=None),
        x_correlation_id: str | None = Header(default=None),
        x_operation_id: str | None = Header(default=None),
        x_idempotency_key: str | None = Header(default=None),
    ):
        context = request_context(authorization, x_correlation_id, x_operation_id, x_idempotency_key)
        job, stored = load_job(job_id, context)
        from modal_service.catalog import POSE_CATALOG_VERSION, validate_pose_choices

        if request.catalog_version != POSE_CATALOG_VERSION:
            raise error_response(WebV2Error("POSE_CATALOG_INCOMPATIBLE", "The selected pose catalog is incompatible.", 409))
        try:
            validate_pose_choices(request.pose_choices)
        except ValueError as error:
            raise error_response(WebV2Error("POSE_CHOICES_INVALID", "The selected poses are invalid.")) from error
        if remember_operation(job_id, context, "poses"):
            return serialize(job, context, stored, replay=True)
        capability = dependencies.capabilities()
        if not bool(capability["poses"]["ready"]):
            raise error_response(WebV2Error("POSE_GENERATION_UNAVAILABLE", "Pose generation is not ready.", 409))
        stored["pose_choices"] = request.pose_choices
        dependencies.operations[job_context_key(job_id)] = stored
        scheduled = dependencies.schedule_poses(
            job_id, context["owner_id"], request.pose_choices, request.catalog_version, context["operation_id"]
        )
        if scheduled.get("error_code"):
            raise error_response(WebV2Error(str(scheduled["error_code"]), "Pose generation could not be scheduled.", 409))
        job, stored = load_job(job_id, context)
        return serialize(job, context, stored)

    @service.get("/v2/mascot/jobs/{job_id}/masters/{master_id}")
    async def web_download_master(
        job_id: str,
        master_id: str,
        authorization: str | None = Header(default=None),
        x_correlation_id: str | None = Header(default=None),
        x_operation_id: str | None = Header(default=None),
    ):
        context = request_context(authorization, x_correlation_id, x_operation_id)
        load_job(job_id, context)
        path = dependencies.asset_path(job_id, "masters", f"{master_id}.png")
        if master_id not in {"master_1", "master_2", "master_3"} or not path.is_file():
            raise HTTPException(status_code=404, detail={"code": "MASTER_NOT_FOUND", "message": "Master not found."})
        return FileResponse(path, media_type="image/png", filename=f"{master_id}.png")

    @service.get("/v2/mascot/jobs/{job_id}/poses/{role}")
    async def web_download_pose(
        job_id: str,
        role: str,
        authorization: str | None = Header(default=None),
        x_correlation_id: str | None = Header(default=None),
        x_operation_id: str | None = Header(default=None),
    ):
        context = request_context(authorization, x_correlation_id, x_operation_id)
        load_job(job_id, context)
        if role not in _POSE_ROLES:
            raise HTTPException(status_code=404, detail={"code": "POSE_NOT_FOUND", "message": "Pose not found."})
        manifest = dependencies.asset_path(job_id, "poses", "manifest.json")
        if not manifest.is_file():
            raise HTTPException(status_code=404, detail={"code": "POSE_NOT_FOUND", "message": "Pose not found."})
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        pose = next((item for item in payload.get("poses", []) if item.get("role") == role), None)
        if not pose:
            raise HTTPException(status_code=404, detail={"code": "POSE_NOT_FOUND", "message": "Pose not found."})
        path = dependencies.asset_path(job_id, "poses", Path(str(pose["fileName"])).name)
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != pose.get("sha256"):
            raise HTTPException(status_code=404, detail={"code": "POSE_NOT_FOUND", "message": "Pose not found."})
        return FileResponse(path, media_type="image/png", filename=f"{role}.png")


def _bearer(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise ValueError("missing bearer")
    return authorization.removeprefix("Bearer ").strip()


def _env(name: str, default: str) -> str:
    import os

    return os.getenv(name, default)

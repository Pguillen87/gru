"""Non-GPU live contract probe for the isolated Modal v2 staging app."""

from __future__ import annotations

import base64
from io import BytesIO
import json
import os
import secrets
import time

import httpx
import jwt
from PIL import Image


BASE_URL = os.environ.get("MODAL_MASCOT_API_URL", "").rstrip("/")
SECRET = os.environ.get("PULEIRO_BFF_JWT_SECRET", "")


def access_token(owner: str, attempt_id: str, *, audience: str = "gru-modal", lifetime: int = 90) -> str:
    now = int(time.time())
    return jwt.encode(
        {
            "iss": "puleiro-bff",
            "aud": audience,
            "sub": owner,
            "jti": secrets.token_hex(16),
            "iat": now,
            "exp": now + lifetime,
            "attempt_id": attempt_id,
        },
        SECRET,
        algorithm="HS256",
    )


def fixture_base64() -> str:
    output = BytesIO()
    Image.new("RGB", (256, 256), "#d9b35f").save(output, format="PNG")
    return base64.b64encode(output.getvalue()).decode("ascii")


def request(client: httpx.Client, method: str, path: str, token: str, **kwargs) -> httpx.Response:
    headers = dict(kwargs.pop("headers", {}))
    headers["Authorization"] = f"Bearer {token}"
    return client.request(method, path, headers=headers, **kwargs)


def main() -> None:
    if not BASE_URL or len(SECRET) < 32:
        raise SystemExit("Set MODAL_MASCOT_API_URL and PULEIRO_BFF_JWT_SECRET before running the probe.")
    owner = "staging-probe-owner"
    attempt_id = f"attempt-probe-{secrets.token_hex(12)}"
    token = access_token(owner, attempt_id)
    key = f"register:{owner}:{attempt_id}"
    payload = {"image_base64": fixture_base64(), "content_type": "image/png", "attempt_id": attempt_id}
    with httpx.Client(base_url=BASE_URL, timeout=30) as client:
        health = client.get("/health").json()
        first = request(client, "POST", "/v2/mascot/jobs", token, headers={"X-Idempotency-Key": key}, json=payload)
        first.raise_for_status()
        job = first.json()
        replay = request(client, "POST", "/v2/mascot/jobs", token, headers={"X-Idempotency-Key": key}, json=payload)
        read = request(client, "GET", f"/v2/mascot/jobs/{job['jobId']}", token)
        resume = request(client, "GET", f"/v2/mascot/jobs?attempt_id={attempt_id}", token)
        master = request(client, "POST", f"/v2/mascot/jobs/{job['jobId']}/master-generations", token, headers={"X-Idempotency-Key": "blocked-master"})
        poses = request(client, "POST", f"/v2/mascot/jobs/{job['jobId']}/pose-generations", token, headers={"X-Idempotency-Key": "blocked-poses"})
    result = {
        "environment": health.get("environment"),
        "generationEnabled": health.get("generation_enabled"),
        "registered": first.status_code == 202 and job.get("generationScheduled") is False,
        "idempotent": replay.json().get("jobId") == job["jobId"] and replay.json().get("idempotentReplay") is True,
        "read": read.status_code == 200,
        "resume": resume.status_code == 200 and resume.json().get("jobId") == job["jobId"],
        "masterBlocked": master.status_code == 409,
        "posesBlocked": poses.status_code == 409,
    }
    print(json.dumps(result, indent=2))
    checks = {key: value for key, value in result.items() if key not in {"environment", "generationEnabled"}}
    if result["environment"] != "staging" or result["generationEnabled"] is not False or not all(checks.values()):
        raise SystemExit("Staging probe failed.")


if __name__ == "__main__":
    main()

# API contract

`GET /health` is public and never schedules work. Every `/v1/mascot/**` request requires both:

- `Authorization: Bearer <Firebase ID token>`
- `X-Firebase-AppCheck: <Firebase App Check token>`

Cost-sensitive writes also require `X-Idempotency-Key`. The verified Firebase UID is the owner; no client-provided user ID is accepted.

## Endpoints

- `POST /v1/mascot/jobs` — requires `consent_policy_version=image-processing-v1`, validates and stores an image, then returns a job. With generation disabled the state is `READY_FOR_GENERATION`.
- `GET /v1/mascot/jobs/{job_id}` — returns only the owner's job.
- `GET /v1/mascot/idempotency/{key}` — recovers a create whose response was lost, for the same authenticated UID.
- `POST /v1/mascot/jobs/{job_id}/approve-master` — approves one Master idempotently.
- `POST /v1/mascot/jobs/{job_id}/cancel` — records server-side cancellation idempotently.
- `DELETE /v1/mascot/jobs/{job_id}` — owner-only, idempotently removes all remote job assets/state and emits only a minimal deletion receipt.
- `GET /v1/mascot/jobs/{job_id}/masters/{master_id}` — authenticated, owner-only image stream.
- `GET /v1/mascot/jobs/{job_id}/result` — completed pose-set manifest.
- `GET /v1/mascot/jobs/{job_id}/poses/{pose_id}` — authenticated, owner-only, checksum-verified image stream.
- `POST /v1/mascot/jobs/{job_id}/consistency`
- `POST /v1/mascot/jobs/{job_id}/generate-poses`
- `POST /v1/mascot/jobs/{job_id}/retry-pose`

The last three endpoints return `TEMPLATE_ASSETS_UNAVAILABLE` until a validated administrator-installed package is active. If templates exist but the kill switch is off, they return `GENERATION_DISABLED`. The evaluator and paid pose worker remain intentionally unavailable until product templates and evaluation tooling are approved.

## Typed image references

Master entries contain `id`, `download_path`, and `sha256`. Result poses contain `poseId`, `name`, `fileName`, `sha256`, and an API-issued `downloadPath`. Internal Volume paths and public bucket URLs are never returned.

## Puleiro BFF V2 (Web only)

`/v2/mascot/**` is an additive, private contract for the Puleiro Web BFF. It
does **not** replace or change Android `/v1/mascot/**` routes.

- Authentication: short-lived HS256 JWT from the BFF; it must contain `sub`
  (owner), `attempt_id`, `iss=puleiro-bff`, `aud=gru-modal`, `iat`, and `exp`.
- Every request also carries `X-Correlation-Id: puleiro_*`; mutations require
  `X-Idempotency-Key`. `X-Operation-Id` is accepted for correlation.
- The server verifies JWT owner + persisted attempt + job ownership on every
  read, write, and asset stream. A valid BFF JWT alone never grants access to
  another attempt.
- `POST /v2/mascot/jobs` registers only. `POST .../master-generations` starts
  the existing job and returns its idempotent state. `GET ...?attempt_id=`
  reconciles a lost response without another upload or GPU request.
- Health probes: `/v2/mascot/health/live`, `/ready`, and `/generation` report
  contract `v2`, dependency readiness, and whether generation is enabled.
- Pose generation remains deliberately gated with `POSE_GENERATION_DISABLED`
  until the approved templates and worker are available; it never returns a
  fabricated pose set.

V2 requires the Modal Secret `gru-mascot-bff-jwt` containing
`MODAL_BFF_JWT_SECRET` (32+ characters). Optional issuer/audience values use
the same names as the BFF configuration. Do not put this secret in a browser
environment variable.

## Errors

Errors use `{"detail":{"code":"...","message":"..."}}`. Rate limits also return `429` and `Retry-After`. Relevant codes include `UNAUTHENTICATED`, `APP_CHECK_REQUIRED`, `CONSENT_REQUIRED`, `INVALID_IMAGE`, `JOB_NOT_FOUND`, `RATE_LIMITED`, `COST_LIMIT_REACHED`, `WORKER_LOST`, `GENERATION_DISABLED`, and `TEMPLATE_ASSETS_UNAVAILABLE`.

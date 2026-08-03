# API contract

`GET /health` is public and never schedules work. Every `/v1/mascot/**` request requires both:

- `Authorization: Bearer <Firebase ID token>`
- `X-Firebase-AppCheck: <Firebase App Check token>`

Cost-sensitive writes also require `X-Idempotency-Key`. The verified Firebase UID is the owner; no client-provided user ID is accepted.

## Endpoints

- `POST /v1/mascot/jobs` — validates and stores an image, then returns a job. With generation disabled the state is `READY_FOR_GENERATION`.
- `GET /v1/mascot/jobs/{job_id}` — returns only the owner's job.
- `GET /v1/mascot/idempotency/{key}` — recovers a create whose response was lost, for the same authenticated UID.
- `POST /v1/mascot/jobs/{job_id}/approve-master` — approves one Master idempotently.
- `POST /v1/mascot/jobs/{job_id}/cancel` — records server-side cancellation idempotently.
- `GET /v1/mascot/jobs/{job_id}/masters/{master_id}` — authenticated, owner-only image stream.
- `GET /v1/mascot/jobs/{job_id}/result` — completed pose-set manifest.
- `GET /v1/mascot/jobs/{job_id}/poses/{pose_id}` — authenticated, owner-only, checksum-verified image stream.
- `POST /v1/mascot/jobs/{job_id}/consistency`
- `POST /v1/mascot/jobs/{job_id}/generate-poses`
- `POST /v1/mascot/jobs/{job_id}/retry-pose`

The last three endpoints return `TEMPLATE_ASSETS_UNAVAILABLE` until a validated administrator-installed package is active. If templates exist but the kill switch is off, they return `GENERATION_DISABLED`. The evaluator and paid pose worker remain intentionally unavailable until product templates and evaluation tooling are approved.

## Typed image references

Master entries contain `id`, `download_path`, and `sha256`. Result poses contain `poseId`, `name`, `fileName`, `sha256`, and an API-issued `downloadPath`. Internal Volume paths and public bucket URLs are never returned.

## Errors

Errors use `{"detail":{"code":"...","message":"..."}}`. Relevant codes include `UNAUTHENTICATED`, `APP_CHECK_REQUIRED`, `INVALID_IMAGE`, `JOB_NOT_FOUND`, `RATE_LIMITED`, `COST_LIMIT_REACHED`, `GENERATION_DISABLED`, and `TEMPLATE_ASSETS_UNAVAILABLE`.

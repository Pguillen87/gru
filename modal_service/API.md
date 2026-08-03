# API

All mascot endpoints except `/health` require `Authorization: Bearer <Firebase ID Token>`.
The service verifies the Firebase signature, issuer, audience and expiry, then derives job
ownership from the verified UID. Cost-bearing writes also require `X-Idempotency-Key`.
The client must never send a user id or any Modal credential.

`consistency`, `generate-poses`, and `retry-pose` are contract endpoints. They return
`TEMPLATE_ASSETS_UNAVAILABLE` until the approved pose-reference assets are installed; this guard
prevents accidental GPU work while the visual templates are pending.

All endpoints require Modal proxy authentication in development. The future GRU control plane must authenticate the end user and inject `X-GRU-User-Id`; it must also create a unique `X-Idempotency-Key` for every cost-bearing operation.

## Implemented

- `GET /health`
- `POST /v1/mascot/jobs`
- `GET /v1/mascot/jobs/{job_id}`
- `POST /v1/mascot/jobs/{job_id}/approve-master`

`POST /v1/mascot/jobs` accepts base64 JPEG, PNG, or WebP for development. Production replaces it with signed, private object upload while preserving the job contract.

## Reserved contract

- `POST /v1/mascot/jobs/{job_id}/consistency`
- `POST /v1/mascot/jobs/{job_id}/generate-poses`
- `POST /v1/mascot/jobs/{job_id}/retry-pose`
- `POST /v1/mascot/jobs/{job_id}/cancel`
- `GET /v1/mascot/jobs/{job_id}/result`

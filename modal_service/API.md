# API

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

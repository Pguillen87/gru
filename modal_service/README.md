# GRU Mascot on Modal

Private, asynchronous backend for validating a pet photo, creating a resumable job, and—only when explicitly enabled—generating Master mascots and versioned poses.

## Safe default

`GRU_MASCOT_ENV` is mandatory. `GPU_GENERATION_ENABLED` remains `false` in development, staging, and production until an operator performs the paid smoke gate. With that value, `POST /v1/mascot/jobs` validates authentication, App Check, consent, image bytes, idempotency, ownership, storage, and job quota, then stops at `READY_FOR_GENERATION`. It does not reserve generation cost or call a GPU function.

## Local verification

```powershell
python -m pytest modal_service/tests
python -m compileall modal_service
```

## Before deployment

1. Create the Modal Secret `gru-mascot-firebase-admin` with the single key `FIREBASE_ADMIN_CREDENTIALS_JSON`. Use the Modal dashboard or a temporary ignored dotenv file; never commit the service-account JSON or place it in a command that will remain in shell history.
2. Create the Modal Secret `gru-mascot-bff-jwt` with `MODAL_BFF_JWT_SECRET` (the same 32+ character server secret configured in the Puleiro BFF). This enables only the Web V2 boundary; Android keeps using Firebase/App Check on V1.
3. Confirm `modal secret list` contains both secret names.
4. Force the safe flag in the deployment shell:

```powershell
$env:GRU_MASCOT_ENV='production'
$env:GPU_GENERATION_ENABLED='false'
modal deploy -m modal_service.app
```

The deployment must not proceed if the Firebase Admin Secret is absent. See [OPERATIONS.md](OPERATIONS.md), [API.md](API.md), and [FIRST_GPU_SMOKE.md](FIRST_GPU_SMOKE.md).

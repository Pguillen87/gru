# GRU Mascot on Modal

Private, asynchronous backend for validating a pet photo, creating a resumable job, and—only when explicitly enabled—generating Master mascots and versioned poses.

## Safe default

`GPU_GENERATION_ENABLED` is `false` in development, staging, and production. With that value, `POST /v1/mascot/jobs` validates authentication, App Check, image bytes, idempotency, ownership, storage, and job quota, then stops at `READY_FOR_GENERATION`. It does not reserve generation cost or call a GPU function.

## Local verification

```powershell
python -m pytest modal_service/tests
python -m compileall modal_service
```

## Before deployment

1. Create the Modal Secret `gru-mascot-firebase-admin` with the single key `FIREBASE_ADMIN_CREDENTIALS_JSON`. Use the Modal dashboard or a temporary ignored dotenv file; never commit the service-account JSON or place it in a command that will remain in shell history.
2. Confirm `modal secret list` contains the secret name.
3. Force the safe flag in the deployment shell:

```powershell
$env:GRU_MASCOT_ENV='development'
$env:GPU_GENERATION_ENABLED='false'
modal deploy -m modal_service.app
```

The deployment must not proceed if the Firebase Admin Secret is absent. See [OPERATIONS.md](OPERATIONS.md), [API.md](API.md), and [FIRST_GPU_SMOKE.md](FIRST_GPU_SMOKE.md).
# Contrato Puleiro v2

A integração segura, não geradora e owner-scoped está documentada em [API_V2.md](API_V2.md). Nenhum deploy é implícito: testes locais não acionam GPU.

O contrato v2 também exige confirmação explícita da categoria do sujeito antes do Master e separa a escolha de três poses da aprovação. Pessoa, animal e objeto recebem instruções de preservação distintas; a geração seletiva de poses permanece protegida por kill switch.

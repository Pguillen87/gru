# GRU Mascot Modal

Serverless generation service for a user-approved pet mascot and its pose library.

## Boundaries

- The service produces masters, consistency samples, and poses.
- It never maps a pose to an Android state.
- The mobile client must not contain Modal credentials.

## Local verification

```powershell
python -m pytest modal_service/tests
python -m compileall modal_service
```

## Deployment

Development endpoints use Modal proxy authentication. Production deployment additionally requires the `gru-mascot-api-auth` Modal secret with `GRU_MASCOT_API_TOKEN` set by the control plane owner.

```powershell
modal deploy modal_service/app.py
```

GPU work is disabled until a job reaches its explicit generation state and passes the configured cost guard.

# Operations

## Firebase Admin Secret

Create `gru-mascot-firebase-admin` in the Modal dashboard with the key `FIREBASE_ADMIN_CREDENTIALS_JSON` and the compact service-account JSON as its value. Restrict access to operators. Do not commit, log, paste into Android, or retain an unencrypted copy in the repository.

## Protected deployment

```powershell
modal profile current
modal secret list
$env:GRU_MASCOT_ENV='development'
$env:GPU_GENERATION_ENABLED='false'
modal deploy -m modal_service.app
```

After deploy, `/health` must report `generation_enabled: false`. If it does not, stop and roll back before any write test.

## Smoke without GPU

Using a registered Debug Android app and Firebase App Check debug token:

1. call `/health`;
2. confirm missing/invalid ID token and App Check return 401;
3. create one job and confirm `READY_FOR_GENERATION`;
4. replay the same UID/idempotency key and confirm the same `job_id`;
5. confirm a different UID receives `JOB_NOT_FOUND`;
6. resume and cancel the job;
7. confirm pose endpoints return the template guard;
8. confirm Modal has no GPU task and no generation-cost reservation.

## Templates

Prepare a package matching `pose_templates/README.md`, then run:

```powershell
python -m modal_service.tools.install_pose_templates C:\approved\gru-pose-package
```

Validation and upload are CPU-only. The active pointer is published last, so an incomplete upload cannot activate a partial package.

## Rollback

Inspect versions with `modal app history gru-mascot`, then run `modal app rollback gru-mascot` for the previous version or supply an audited version identifier. Recheck `/health` after rollback.

## Cost inspection

Use Modal workspace metrics and credits pages plus the `gru-mascot-usage` Dict counters once the new deployment is active. Job quota and estimated generation-cost reservation are separate. With generation disabled, no `global-cost:*` or `user-cost:*` counter is created.

## Retention

Originals and rejected Masters are temporary. Approved Masters and poses are private persistent assets. Cleanup must remain idempotent and job-scoped; no cleanup deployment is enabled until retention durations are product-approved.

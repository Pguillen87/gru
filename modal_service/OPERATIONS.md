# Operations

## Firebase Admin Secret

Create `gru-mascot-firebase-admin` in the Modal dashboard with the key `FIREBASE_ADMIN_CREDENTIALS_JSON` and the compact service-account JSON as its value. Restrict access to operators. Do not commit, log, paste into Android, or retain an unencrypted copy in the repository.

If the credential does not exist yet:

1. Open Firebase Console > `gru-mascote` > Project settings > Service accounts.
2. Generate a new private key for the server-side Admin SDK and download it locally.
3. Open Modal > workspace `automacao-guillenia` > Secrets > Create secret.
4. Name it `gru-mascot-firebase-admin`, add `FIREBASE_ADMIN_CREDENTIALS_JSON`, and paste the complete JSON value directly in the protected Modal form.
5. Delete or securely archive the downloaded JSON after the Secret is confirmed. Never paste it into chat or a shell command.

The Secret is used only by the Modal API to verify Firebase ID tokens and App Check proofs. It is never an Android credential.

## Firebase Debug Android app

The debug variant must be a separate Firebase Android app. If CLI access returns `403 PERMISSION_DENIED`, use an account with project administration access and:

1. Open Firebase Console > `gru-mascote` > Project settings > General.
2. Select Add app > Android.
3. Register package `com.pguillen.gru.debug` (suggested nickname: `GRU Debug`).
4. Download its `google-services.json`.
5. Save it only as `app/src/debug/google-services.json`.

Do not remove the debug `applicationIdSuffix` and do not copy the release configuration into the debug source set. SHA certificates are not needed for Anonymous Auth or the App Check Debug provider. For the release Play Integrity provider, finish the Play Console/Firebase App Check registration for the signed release app, including the release SHA-256 certificate required by that integration.

After the debug build starts, capture the official App Check debug token from Logcat, register it in Firebase Console > App Check > Apps > Manage debug tokens, and keep it out of Git, resources, and release builds.

## Protected deployment

```powershell
modal profile current
modal secret list
$env:GRU_MASCOT_ENV='development'
$env:GPU_GENERATION_ENABLED='false'
modal deploy -m modal_service.app
```

After deploy, `/health` must report `generation_enabled: false`. If it does not, stop and roll back before any write test.

## Model cache administration

The persistent worker never downloads Hugging Face artifacts during a user generation. Prepare the pinned cache as a separate CPU-only operation while generation remains disabled:

```powershell
modal run -m modal_service.app::prepare_model_cache
modal run -m modal_service.app::model_cache_status
```

The first command can transfer approximately 54–55 GiB when the Volume is empty. It does not request a GPU, but it can consume network, CPU, storage and execution time. Inspect the returned revision, file count and expected size before enabling generation.

`MODEL_CACHE_NOT_READY` means the active pointer, READY marker, manifest or expected file inventory failed validation. Do not bypass this guard or enable Hugging Face downloads inside `QwenMasterWorker`.

Previous manifests and artifacts are retained. A rollback pointer can be selected administratively:

```powershell
modal run -m modal_service.app::activate_model_cache_revision --cache-revision <audited-revision>
```

The deployed code must recognize the selected model/LoRA revisions. Prefer rolling back the Modal App version together with its matching cache revision.

## Persistent worker policy

Development uses H100, `min_containers=0`, `max_containers=1`, `buffer_containers=0`, `scaledown_window=45` and one input per container. Do not increase capacity or keep a permanent warm container before the benchmark and economic review.

Logs use `modal_inference` JSON with a sanitized `trace_id`. Correlate `job_queued`, `job_started`, `worker_ready`, `master_generated` and `job_completed`. Modal billing and queue metrics remain authoritative for billed GPU seconds and platform queue depth.

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

## Safe request diagnostics

Android request telemetry uses the `GruMascot` Logcat tag. It records only the
pipeline stage, duration, response status, structured API code, request ID and
payload sizes. It must never contain the photo, selected URI, Firebase UID,
Bearer token, App Check proof, idempotency key, complete private URL or raw
exception message.

Capture one reproduction from the connected debug device with:

```powershell
$adb = "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe"
& $adb logcat -c
& $adb logcat -v threadtime GruMascot:V FirebaseAuth:V FirebaseAppCheck:V DebugAppCheckProvider:V '*:S'
```

Correlate an Android response with Modal through the short `X-Request-ID`
returned by the API. Server logs use `event=http_request` and include only the
request ID, method, normalized endpoint name, status, duration and content
length:

```powershell
modal app logs gru-mascot --timestamps
```

Interpret the main Android events in order: `photo_read`, `auth_token`,
`app_check_token`, `create_prepare`, `http_complete`, and `create_complete`.
If `http_complete` is absent, the request did not receive an HTTP response. If
it has a request ID, use that value to locate the corresponding server entry.
Keep `GPU_GENERATION_ENABLED=false` throughout diagnostics unless a separately
authorized paid smoke is being performed.

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

Development permits a small number of CPU-only validation jobs per UID so
cancel/retry testing does not consume the single paid-smoke allowance. Paid
generation has its own `user-generations:*` quota and remains limited to one
generation per UID/day in development, in addition to the global and per-user
cost caps. Enabling GPU generation is still a separate explicit operation.

## Retention

Originals and rejected Masters are temporary. Approved Masters and poses are private persistent assets. Cleanup must remain idempotent and job-scoped; no cleanup deployment is enabled until retention durations are product-approved.

## Play Store release gate

Before publishing the mascot feature, execute and archive the mandatory release
and LGPD audit defined in `SECURITY.md`. This is a blocking operational gate,
not a post-release task. At minimum, the operator must retain evidence for Play
Integrity on `com.pguillen.gru`, release-artifact credential scanning, EXIF
removal, informed consent, approved retention periods, end-to-end deletion, and
confirmation that Firebase Admin and Modal credentials are absent from the
APK/AAB. Debug App Check tokens are development-only and must never be copied
into source code, Android resources, Git, or a release artifact.

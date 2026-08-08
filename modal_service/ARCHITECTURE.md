# Architecture

The Modal app owns asynchronous mascot work only. Android owns the mapping from runtime state to a downloaded local pose.

## Components

- `domain.py`: centralized job states and legal transitions.
- `coordinator.py`: serialized job idempotency, UID ownership, job quota, and generation-cost reservation.
- `app.py`: authenticated ASGI API, private asset streaming, and GPU boundary.
- `model_cache.py`: pinned cache manifest, READY marker, validation and rollback pointer.
- `persistent_runtime.py`: load-once lifecycle and worker health boundary.
- `inference_observability.py`: sanitized trace and latency events.
- `templates.py` plus `tools/install_pose_templates.py`: administrator-only versioned pose package activation.
- Android `MascotApi`/`MascotRepository`: typed contract, stable operation keys, polling/resume/cancel.
- Android `CustomMascotStore`: checksum validation, staging, atomic promotion, and offline files.

## Resources

- `gru-mascot-assets` Volume: private originals, Masters, consistency artifacts, pose sets, and template packages.
- `gru-mascot-models` Volume: model cache only.
- `gru-mascot-jobs` Dict: operational job state.
- `gru-mascot-idempotency` Dict: create and operation replay protection.
- `gru-mascot-usage` Dict: separate job-count and generation-cost ledgers.
- `gru-mascot-firebase-admin` Secret: server-only Firebase Admin credential.

## Lifecycle

`create -> READY_FOR_GENERATION -> generate Masters -> explicit Master approval -> consistency -> approved six-pose MVP -> result`.

With the kill switch off, the lifecycle stops honestly at `READY_FOR_GENERATION`. Closing Android does not cancel; it persists `job_id` and resumes polling. Network failure preserves the pending job. Explicit cancellation is confirmed by the server before local state is cleared.

When generation is enabled, a CPU-only cache guard runs before cost reservation. `QwenMasterWorker` loads the pinned local cache once in `@modal.enter()` and processes one input at a time. The pipeline remains container-scoped; job state remains in Modal Dicts. Development scales from zero to one container with a 45-second scaledown window.

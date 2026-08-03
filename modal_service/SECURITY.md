# Security

- Android sends short-lived Firebase Anonymous ID tokens and App Check proofs; it contains no Modal or Firebase Admin credential.
- Release includes only Play Integrity App Check code. Debug includes only the official Debug App Check provider.
- The API validates Firebase signature, expiry, audience `gru-mascote`, issuer, and UID, then validates App Check before executing endpoint code.
- Invalid or missing authentication is rejected before image storage, quota mutation, job creation, cost reservation, or GPU scheduling.
- Ownership failures return the same safe `JOB_NOT_FOUND` behavior and expose no state, image, Master, or result metadata.
- Create IDs are deterministic for UID plus idempotency key. Approval and cancellation use stable operation keys and idempotent domain transitions.
- Per-UID/global job count, per-UID generation cost, and global generation cost are separate guards. A serialized coordinator prevents concurrent check/update races.
- `GPU_GENERATION_ENABLED` defaults to false everywhere. Both the API scheduler and GPU function enforce it.
- Master and pose images are streamed through authenticated owner-only endpoints; the Volume is not public or enumerable.
- Tokens, images, private download references, and credentials are never logged.
- Official pose templates can be installed only by an operator, never by the APK.

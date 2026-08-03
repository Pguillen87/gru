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

## Mandatory Play Store and LGPD release gate

Publishing the mascot feature in the Play Store is blocked until a release and
privacy audit is completed, evidenced, and approved. The audit must verify all
of the following:

- the release package `com.pguillen.gru` uses Firebase App Check with Play
  Integrity, the production signing SHA-256 is registered, and no release path
  can select the Debug App Check provider;
- the final APK/AAB and its merged resources contain no Modal credential,
  Firebase Admin service-account material, private key, App Check debug token,
  development endpoint secret, or other administrative credential;
- image metadata, including EXIF and location data, is removed before upload,
  and the backend rejects or sanitizes metadata-bearing inputs as defense in
  depth;
- the user gives informed, purpose-specific consent before the pet photo is
  uploaded, including disclosure of cloud processing and the relevant service
  providers;
- approved retention periods exist for originals, rejected Masters, approved
  Masters, poses, temporary files, job metadata, and operational logs, with an
  idempotent cleanup routine verified against those periods;
- a user-accessible deletion flow removes local files and requests deletion of
  the corresponding remote original, derivatives, job metadata, and ownership
  records, with failure recovery and auditable completion;
- the privacy notice documents purpose, legal basis, controller/operator roles,
  data-subject rights, retention, deletion, international processing where
  applicable, and a contact channel required by LGPD;
- release evidence includes consent UX captures, EXIF-removal tests, retention
  and deletion tests, App Check/Play Integrity validation, dependency and
  secret scans, and an APK/AAB inspection report.

No production rollout, GPU enablement for public clients, or Play Store release
may proceed while any item in this gate is incomplete.

# Security

- Android authenticates with a short-lived Firebase Anonymous ID token; no Modal token is shipped.
- The ASGI service validates Firebase signature, issuer, audience (`gru-mascote`) and expiry before it uses a UID.
- The UID, never a client-supplied user header, owns jobs and idempotency records.
- Firebase tokens, source images, signed URLs and secrets are excluded from application logs.
- Cost-bearing operations require Firebase App Check in addition to the Firebase ID token. Android uses Play Integrity in release and Firebase's official debug provider only in debug builds.
- The service applies a per-UID daily job and cost quota before the global daily cost cap. The global cap remains the final financial guard.
- A Firebase Admin credential is not committed. If operational administration later requires one, it must be created only as a Modal Secret.

- Modal credentials never enter the Android application.
- Development endpoint uses Modal proxy authentication.
- Production requires an external authenticated GRU control plane and private, signed object exchange.
- MIME is verified from bytes, not from the request label.
- Storage paths are generated server-side and are never returned.
- Logs must contain identifiers and durations only, never tokens, signed URLs, prompt contents, or image bytes.

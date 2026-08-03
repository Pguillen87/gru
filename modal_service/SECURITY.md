# Security

- Modal credentials never enter the Android application.
- Development endpoint uses Modal proxy authentication.
- Production requires an external authenticated GRU control plane and private, signed object exchange.
- MIME is verified from bytes, not from the request label.
- Storage paths are generated server-side and are never returned.
- Logs must contain identifiers and durations only, never tokens, signed URLs, prompt contents, or image bytes.

# Operations

## Initial state

The Modal workspace was inspected before implementation: no applications, secrets, or volumes existed. The Modal client is 1.3.0.post1.

## Deployment

Deploy with the active Modal profile. Deployment creates the named Volumes and Dicts lazily. GPU inference is charged only when generation is scheduled.

## Retention

Originals and rejected masters are temporary. Approved masters and poses require an external durable storage decision before production. Cleanup must be idempotent and delete only job-scoped prefixes after the configured retention period.
# Abuse and cost guards

Before enabling GPU traffic, enable Firebase App Check enforcement for the Android application in Firebase Console. Add the official debug token only to the Firebase App Check debug allowlist; never put it in the APK or repository. The API refuses cost-bearing requests without an App Check token.

Each environment has an explicit per-UID job limit and cost cap in `config.py`, in addition to its global cost cap and Modal container limit. These values are deliberately small in development.

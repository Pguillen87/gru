# Firebase authentication and App Check

Android authenticates anonymously with Firebase, obtains a short-lived ID token, then obtains an App Check token. The backend validates both before it processes a protected endpoint.

The release package is `com.pguillen.gru`; the debug package is `com.pguillen.gru.debug`. Each must be registered as a separate Android app in Firebase project `gru-mascote`. Release uses Play Integrity. Debug uses only Firebase's official Debug provider.

The server Secret `gru-mascot-firebase-admin` must expose `FIREBASE_ADMIN_CREDENTIALS_JSON`. It is never stored in Git, Android resources, BuildConfig, preferences, or logs. Deployment remains blocked until this Secret exists.

See `FIREBASE_DEBUG.md` for the current debug-app permission blocker.

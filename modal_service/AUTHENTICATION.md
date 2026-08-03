# Firebase authentication rollout

The deployed API originally used Modal proxy authentication, which an Android APK cannot use safely.
The application code now expects `Authorization: Bearer <Firebase ID Token>` and verifies the
token against the `gru-mascote` Firebase project. Redeploy only after reviewing the change; no
Modal account or proxy token belongs in Android.

The Android release configuration is registered as `com.pguillen.gru`. Debug retains its
`com.pguillen.gru.debug` suffix and must be registered as a separate Firebase Android app before
debug Firebase builds or device validation. Do not remove the suffix as a workaround.

The Modal secret named `gru-mascot-firebase-admin` must contain only the Firebase service-account
JSON in `FIREBASE_ADMIN_CREDENTIALS_JSON`. It is required exclusively by the server to verify
Firebase App Check. Do not deploy this authentication revision until that secret exists.

# Firebase Debug configuration

The release app remains `com.pguillen.gru`. Debug remains `com.pguillen.gru.debug`; do not remove `applicationIdSuffix`.

1. In Firebase Console, open project `gru-mascote`.
2. Project settings → Your apps → Add app → Android.
3. Register package `com.pguillen.gru.debug` (suggested nickname: `GRU Debug`).
4. Download that app's `google-services.json`.
5. Place it at `app/src/debug/google-services.json`.
6. In App Check, register the Debug provider token printed by the debug build only for development testing.

The current CLI account receives HTTP 403 `PERMISSION_DENIED` from `projects/gru-mascote:searchApps`; an account with permission to list and create Firebase Android apps in this project must perform the registration. Do not copy the release JSON into the debug variant.

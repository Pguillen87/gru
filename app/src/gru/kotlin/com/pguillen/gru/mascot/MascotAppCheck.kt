package com.pguillen.gru.mascot

import com.google.firebase.appcheck.FirebaseAppCheck
import kotlinx.coroutines.tasks.await

interface MascotAppCheckTokenProvider {
    suspend fun token(): String
}

class FirebaseMascotAppCheckTokenProvider(
    private val appCheck: FirebaseAppCheck = FirebaseAppCheck.getInstance(),
) : MascotAppCheckTokenProvider {
    override suspend fun token(): String = appCheck.getAppCheckToken(false).await().token
}

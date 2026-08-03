package com.pguillen.gru.mascot

import com.google.firebase.appcheck.FirebaseAppCheck
import kotlinx.coroutines.tasks.await

interface MascotAppCheckTokenProvider {
    suspend fun token(): String
}

class FirebaseMascotAppCheckTokenProvider(
    private val appCheck: FirebaseAppCheck? = null,
) : MascotAppCheckTokenProvider {
    override suspend fun token(): String = try {
        (appCheck ?: FirebaseAppCheck.getInstance()).getAppCheckToken(false).await().token
    } catch (error: IllegalStateException) {
        throw MascotFirebaseConfigurationException(error)
    } catch (error: Exception) {
        throw MascotAppCheckException(error)
    }
}

class MascotAppCheckException(cause: Throwable) : Exception("Unable to validate the application.", cause)

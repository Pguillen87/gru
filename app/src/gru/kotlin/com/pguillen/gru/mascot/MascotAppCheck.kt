package com.pguillen.gru.mascot

import com.google.firebase.appcheck.FirebaseAppCheck
import kotlinx.coroutines.tasks.await

interface MascotAppCheckTokenProvider {
    suspend fun token(): String
}

class FirebaseMascotAppCheckTokenProvider(
    private val appCheck: FirebaseAppCheck? = null,
) : MascotAppCheckTokenProvider {
    override suspend fun token(): String {
        val started = MascotTelemetry.mark()
        return try {
            (appCheck ?: FirebaseAppCheck.getInstance()).getAppCheckToken(false).await().token.also {
                MascotTelemetry.info("app_check_token", started, mapOf("outcome" to "success"))
            }
        } catch (error: IllegalStateException) {
            throw MascotFirebaseConfigurationException(error).also {
                MascotTelemetry.failure("app_check_token", started, it)
            }
        } catch (error: Exception) {
            throw MascotAppCheckException(error).also { MascotTelemetry.failure("app_check_token", started, it) }
        }
    }
}

class MascotAppCheckException(cause: Throwable) : Exception("Unable to validate the application.", cause)

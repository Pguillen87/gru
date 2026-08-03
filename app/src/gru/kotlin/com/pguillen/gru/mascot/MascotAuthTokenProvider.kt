package com.pguillen.gru.mascot

import com.google.firebase.auth.FirebaseAuth
import kotlinx.coroutines.tasks.await

interface MascotAuthTokenProvider {
    suspend fun token(): String
}

class FirebaseMascotAuthTokenProvider(
    private val auth: FirebaseAuth? = null,
) : MascotAuthTokenProvider {
    override suspend fun token(): String {
        val started = MascotTelemetry.mark()
        try {
            val firebaseAuth = auth ?: FirebaseAuth.getInstance()
            val reusedIdentity = firebaseAuth.currentUser != null
            val user = firebaseAuth.currentUser ?: firebaseAuth.signInAnonymously().await().user
                ?: throw MascotAuthException("Unable to create a secure identity.")
            return (user.getIdToken(false).await().token
                ?: throw MascotAuthException("Unable to validate the secure identity.")
            ).also {
                MascotTelemetry.info("auth_token", started, mapOf("outcome" to "success", "identity_reused" to reusedIdentity))
            }
        } catch (error: MascotAuthException) {
            MascotTelemetry.failure("auth_token", started, error)
            throw error
        } catch (error: IllegalStateException) {
            throw MascotFirebaseConfigurationException(error).also { MascotTelemetry.failure("auth_token", started, it) }
        } catch (error: Exception) {
            throw MascotAuthException("Unable to validate the secure identity.", error)
                .also { MascotTelemetry.failure("auth_token", started, it) }
        }
    }
}

class MascotAuthException(message: String, cause: Throwable? = null) : Exception(message, cause)
class MascotFirebaseConfigurationException(cause: Throwable) : Exception("Firebase is not configured.", cause)

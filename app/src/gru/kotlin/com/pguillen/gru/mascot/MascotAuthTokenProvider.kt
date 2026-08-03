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
        try {
            val firebaseAuth = auth ?: FirebaseAuth.getInstance()
            val user = firebaseAuth.currentUser ?: firebaseAuth.signInAnonymously().await().user
                ?: throw MascotAuthException("Unable to create a secure identity.")
            return user.getIdToken(false).await().token
                ?: throw MascotAuthException("Unable to validate the secure identity.")
        } catch (error: MascotAuthException) {
            throw error
        } catch (error: IllegalStateException) {
            throw MascotFirebaseConfigurationException(error)
        } catch (error: Exception) {
            throw MascotAuthException("Unable to validate the secure identity.", error)
        }
    }
}

class MascotAuthException(message: String, cause: Throwable? = null) : Exception(message, cause)
class MascotFirebaseConfigurationException(cause: Throwable) : Exception("Firebase is not configured.", cause)

package com.pguillen.gru.mascot

import com.google.firebase.auth.FirebaseAuth
import kotlinx.coroutines.tasks.await

interface MascotAuthTokenProvider {
    suspend fun token(): String
}

class FirebaseMascotAuthTokenProvider(
    private val auth: FirebaseAuth = FirebaseAuth.getInstance(),
) : MascotAuthTokenProvider {
    override suspend fun token(): String {
        val user = auth.currentUser ?: auth.signInAnonymously().await().user
            ?: throw MascotAuthException("Não foi possível criar sua identidade segura.")
        return user.getIdToken(false).await().token
            ?: throw MascotAuthException("Não foi possível validar sua identidade segura.")
    }
}

class MascotAuthException(message: String) : Exception(message)

package com.pguillen.gru.mascot

import com.pguillen.gru.GruPreferences
import java.util.UUID

sealed interface MascotCreationState {
    data object Idle : MascotCreationState
    data object PhotoSelected : MascotCreationState
    data object Submitting : MascotCreationState
    data class Tracking(val job: MascotJobResponse) : MascotCreationState
    data class AwaitingMasterApproval(val job: MascotJobResponse) : MascotCreationState
    data class Failed(val message: String) : MascotCreationState
    data object Canceled : MascotCreationState
}

class MascotRepository(private val api: MascotApi, private val preferences: GruPreferences) {
    suspend fun create(image: ByteArray, mimeType: String): MascotJobResponse {
        val key = preferences.pendingMascotRequestId.value ?: UUID.randomUUID().toString().also(preferences::setPendingMascotRequestId)
        val job = api.createJob(image, mimeType, key)
        preferences.setPendingMascotJobId(job.jobId)
        preferences.setPendingMascotRequestId(null)
        return job
    }

    suspend fun resume(): MascotJobResponse? {
        val jobId = preferences.pendingMascotJobId.value ?: return null
        return api.job(jobId)
    }

    fun clearPending() {
        preferences.setPendingMascotJobId(null)
        preferences.setPendingMascotRequestId(null)
    }

    suspend fun approve(jobId: String, masterId: String): MascotJobResponse = api.approveMaster(jobId, masterId, UUID.randomUUID().toString())
}

fun MascotJobResponse.toCreationState(): MascotCreationState = when (state) {
    "AWAITING_MASTER_APPROVAL" -> MascotCreationState.AwaitingMasterApproval(this)
    "FAILED" -> MascotCreationState.Failed("Não foi possível criar seu mascote. Tente novamente.")
    "CANCELED" -> MascotCreationState.Canceled
    "COMPLETED" -> MascotCreationState.Tracking(this)
    else -> MascotCreationState.Tracking(this)
}

fun mascotErrorMessage(error: Throwable): String = when ((error as? MascotApiException)?.apiError?.code) {
    "UNAUTHENTICATED" -> "Não foi possível confirmar a segurança do aplicativo. Tente novamente."
    "INVALID_IMAGE" -> "Essa foto não pode ser usada. Escolha outra foto do seu pet."
    "COST_LIMIT_REACHED", "RATE_LIMITED" -> "A criação de mascotes está temporariamente indisponível. Tente mais tarde."
    "TEMPLATE_ASSETS_UNAVAILABLE" -> "As poses do mascote ainda estão sendo preparadas."
    "JOB_NOT_FOUND" -> "Não encontramos essa criação. Escolha a foto novamente."
    "MASTER_GENERATION_FAILED" -> "Não foi possível preparar as opções do mascote. Tente novamente."
    else -> if (error is MascotAuthException) "Não foi possível confirmar sua identidade segura. Tente novamente." else "Não foi possível conectar agora. Verifique sua internet e tente novamente."
}

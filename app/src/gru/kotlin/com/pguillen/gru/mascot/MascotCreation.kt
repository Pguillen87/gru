package com.pguillen.gru.mascot

import com.pguillen.gru.GruPreferences
import java.io.IOException
import java.util.UUID
import kotlinx.coroutines.flow.StateFlow

sealed interface MascotCreationState {
    data object Idle : MascotCreationState
    data object PhotoSelected : MascotCreationState
    data object Submitting : MascotCreationState
    data class Tracking(val job: MascotJobResponse) : MascotCreationState
    data class AwaitingMasterApproval(val job: MascotJobResponse) : MascotCreationState
    data class NetworkUnavailable(val jobId: String) : MascotCreationState
    data object SubmissionUncertain : MascotCreationState
    data class RemoteFailed(val message: String) : MascotCreationState
    data object Canceling : MascotCreationState
    data class CancelPending(val jobId: String) : MascotCreationState
    data object Canceled : MascotCreationState
}

class MascotRepository(
    private val api: MascotRemoteApi,
    private val pending: MascotPendingState,
    private val customStore: CustomMascotStore? = null,
) {
    constructor(api: MascotRemoteApi, preferences: GruPreferences, customStore: CustomMascotStore? = null) : this(
        api, GruMascotPendingState(preferences), customStore,
    )

    suspend fun create(image: ByteArray, mimeType: String): MascotJobResponse {
        resume()?.let { existing ->
            if (!existing.isTerminal()) return existing
            clearPending()
        }
        val key = pending.requestId.value
            ?: UUID.randomUUID().toString().also(pending::setRequestId)
        val job = api.createJob(image, mimeType, key)
        pending.setJobId(job.jobId)
        pending.setRequestId(null)
        return job
    }

    suspend fun resume(): MascotJobResponse? {
        val jobId = pending.jobId.value ?: return recoverUnacknowledgedCreate()
        if (pending.cancelPending.value) return cancel(jobId)
        return api.job(jobId)
    }

    private suspend fun recoverUnacknowledgedCreate(): MascotJobResponse? {
        val requestId = pending.requestId.value ?: return null
        return try {
            api.recoverJob(requestId).also { job ->
                pending.setJobId(job.jobId)
                pending.setRequestId(null)
            }
        } catch (error: MascotApiException) {
            if (error.apiError.code == "JOB_NOT_FOUND") throw MascotRecoveryPendingException() else throw error
        }
    }

    suspend fun approve(jobId: String, masterId: String): MascotJobResponse =
        api.approveMaster(jobId, masterId, "approve:$jobId:$masterId")

    suspend fun downloadMaster(reference: MasterReference): ByteArray = api.download(reference.downloadPath).also { bytes ->
        reference.sha256?.let { expected -> require(bytes.matchesSha256(expected)) { "Master checksum does not match." } }
    }

    suspend fun cancel(jobId: String): MascotJobResponse {
        pending.setCancelPending(true)
        val response = api.cancel(jobId, "cancel:$jobId")
        if (response.isTerminal()) clearPending()
        return response
    }

    suspend fun installCompletedMascot(jobId: String): Boolean {
        val store = requireNotNull(customStore)
        val result = api.result(jobId)
        val images = result.poses.associate { pose -> pose.poseId to api.download(requireNotNull(pose.downloadPath)) }
        val defaults = result.poses.take(3).map(MascotPose::poseId)
        if (defaults.size < 3) return false
        val manifest = CustomMascotManifest(
            result.poseSetId, result.masterId, result.version, result.modelVersion, result.poses,
            defaults[0], defaults[1], defaults[2],
        )
        if (!store.promote(manifest, images)) return false
        pending.selectCustomMascot(result.poseSetId, result.masterId)
        clearPending()
        return true
    }

    fun clearPending() {
        pending.setJobId(null)
        pending.setRequestId(null)
        pending.setCancelPending(false)
    }
}

interface MascotPendingState {
    val jobId: StateFlow<String?>
    val requestId: StateFlow<String?>
    val cancelPending: StateFlow<Boolean>
    fun setJobId(value: String?)
    fun setRequestId(value: String?)
    fun setCancelPending(value: Boolean)
    fun selectCustomMascot(poseSetId: String, masterId: String)
}

private class GruMascotPendingState(private val preferences: GruPreferences) : MascotPendingState {
    override val jobId = preferences.pendingMascotJobId
    override val requestId = preferences.pendingMascotRequestId
    override val cancelPending = preferences.mascotCancelPending
    override fun setJobId(value: String?) = preferences.setPendingMascotJobId(value)
    override fun setRequestId(value: String?) = preferences.setPendingMascotRequestId(value)
    override fun setCancelPending(value: Boolean) = preferences.setMascotCancelPending(value)
    override fun selectCustomMascot(poseSetId: String, masterId: String) = preferences.selectCustomMascot(poseSetId, masterId)
}

fun MascotJobResponse.toCreationState(): MascotCreationState = when (state) {
    "AWAITING_MASTER_APPROVAL" -> MascotCreationState.AwaitingMasterApproval(this)
    "FAILED" -> MascotCreationState.RemoteFailed("Não foi possível criar seu mascote. Tente novamente.")
    "CANCELED" -> MascotCreationState.Canceled
    else -> MascotCreationState.Tracking(this)
}

fun Throwable.toMascotFailure(jobId: String?): MascotCreationState = if (isNetworkFailure()) {
    if (jobId == null) MascotCreationState.SubmissionUncertain else MascotCreationState.NetworkUnavailable(jobId)
} else {
    MascotCreationState.RemoteFailed(mascotErrorMessage(this))
}

fun Throwable.isNetworkFailure(): Boolean = this is IOException || cause is IOException

private class MascotRecoveryPendingException : IOException("Mascot create acknowledgement is pending.")

fun MascotJobResponse.isTerminal(): Boolean = state in setOf("COMPLETED", "FAILED", "CANCELED")

fun mascotErrorMessage(error: Throwable): String = when ((error as? MascotApiException)?.apiError?.code) {
    "UNAUTHENTICATED", "APP_CHECK_REQUIRED" -> "Não foi possível confirmar a segurança do aplicativo. Tente novamente."
    "INVALID_IMAGE" -> "Essa foto não pode ser usada. Escolha outra foto do seu pet."
    "COST_LIMIT_REACHED", "RATE_LIMITED" -> "A criação de mascotes está temporariamente indisponível. Tente mais tarde."
    "GENERATION_DISABLED" -> "A criação está temporariamente pausada. Sua solicitação continua salva."
    "TEMPLATE_ASSETS_UNAVAILABLE" -> "As poses do mascote ainda estão sendo preparadas."
    "JOB_NOT_FOUND" -> "Não encontramos essa criação. Escolha a foto novamente."
    "MASTER_GENERATION_FAILED" -> "Não foi possível preparar as opções do mascote. Tente novamente."
    else -> if (error is MascotAuthException) "Não foi possível confirmar sua identidade segura. Tente novamente."
    else "Não foi possível conectar agora. Verifique sua internet e tente novamente."
}

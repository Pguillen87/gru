package com.pguillen.gru.mascot.importing

import com.pguillen.gru.mascot.CustomMascotStore
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

class MascotImportCoordinator(
    private val resolver: MascotCodeResolver,
    private val installer: MascotPackageInstaller,
    private val store: CustomMascotStore,
    private val previewDownloader: MascotAssetDownloader,
    private val verifier: MascotAssetVerifier = MascotAssetVerifier(),
) {
    private val mutableState = MutableStateFlow<MascotImportState>(MascotImportState.Idle)
    private val operationMutex = Mutex()
    val state: StateFlow<MascotImportState> = mutableState.asStateFlow()

    suspend fun resolve(rawCode: String): Unit = operationMutex.withLock {
        val started = MascotImportTelemetry.begin()
        val code = MascotImportCode.parse(rawCode)
        if (code == null) {
            mutableState.value = MascotImportState.InvalidCode
            MascotImportTelemetry.event("import_code_invalid", started)
            return
        }
        mutableState.value = MascotImportState.Resolving
        mutableState.value = when (val result = resolver.resolve(code)) {
            is MascotResolveResult.Found -> result.manifest.validate()?.let(MascotImportState::UnsupportedManifest)
                ?: if (store.isImportedPackageInstalled(
                        result.manifest.mascotId,
                        result.manifest.packageVersion,
                        result.manifest.poses.map { it.sha256 },
                    )) MascotImportState.AlreadyInstalled(result.manifest)
                else loadPreview(result.manifest)
            MascotResolveResult.NotConfigured -> MascotImportState.NotConfigured
            MascotResolveResult.NotFound -> MascotImportState.NotFound
            MascotResolveResult.AccessDenied -> MascotImportState.AccessDenied
            MascotResolveResult.NetworkUnavailable -> MascotImportState.NetworkUnavailable
            is MascotResolveResult.Failed -> MascotImportState.ResolveFailed(result.errorCode)
        }
        MascotImportTelemetry.event("import_resolved", started, mapOf("result" to mutableState.value.javaClass.simpleName))
    }

    suspend fun install(): Unit = operationMutex.withLock {
        val preview = mutableState.value as? MascotImportState.PreviewReady ?: return
        val manifest = preview.manifest
        val started = MascotImportTelemetry.mark()
        MascotImportTelemetry.event("import_install_started")
        mutableState.value = MascotImportState.Downloading(manifest, 0, 3)
        val result = installer.install(
            manifest,
            mapOf(MascotPoseRole.NORMAL to preview.previewBytes),
            onProgress = { completed, total -> mutableState.value = MascotImportState.Downloading(manifest, completed, total) },
            onPhase = { phase -> mutableState.value = when (phase) {
                MascotInstallPhase.VERIFYING -> MascotImportState.Verifying(manifest)
                MascotInstallPhase.INSTALLING -> MascotImportState.Installing(manifest)
            } },
        )
        mutableState.value = when (result) {
            is MascotInstallResult.Installed -> MascotImportState.Installed(manifest, result.packageKey)
            is MascotInstallResult.AlreadyInstalled -> MascotImportState.AlreadyInstalled(manifest)
            is MascotInstallResult.InvalidManifest -> MascotImportState.UnsupportedManifest(result.reason)
            is MascotInstallResult.DownloadFailed -> MascotImportState.DownloadFailed(result.role)
            is MascotInstallResult.IntegrityFailed -> MascotImportState.IntegrityFailed(result.role)
            MascotInstallResult.InstallFailed -> MascotImportState.InstallFailed
        }
        MascotImportTelemetry.event("import_install_finished", started, mapOf("result" to result.javaClass.simpleName))
    }

    fun reset() { mutableState.value = MascotImportState.Idle }

    private suspend fun loadPreview(manifest: MascotImportManifest): MascotImportState {
        val bytes = try { previewDownloader.download(manifest.preview) } catch (cancellation: CancellationException) {
            throw cancellation
        } catch (_: Exception) {
            return MascotImportState.DownloadFailed(MascotPoseRole.NORMAL)
        }
        return if (verifier.verify(manifest.preview, bytes) == VerificationResult.OK) {
            MascotImportState.PreviewReady(manifest, bytes)
        } else MascotImportState.IntegrityFailed(MascotPoseRole.NORMAL)
    }
}

sealed interface MascotImportState {
    data object Idle : MascotImportState
    data object InvalidCode : MascotImportState
    data object Resolving : MascotImportState
    data object NotConfigured : MascotImportState
    data object NotFound : MascotImportState
    data object AccessDenied : MascotImportState
    data object NetworkUnavailable : MascotImportState
    data class ResolveFailed(val code: String) : MascotImportState
    data class UnsupportedManifest(val reason: ManifestValidationError) : MascotImportState
    data class PreviewReady(val manifest: MascotImportManifest, val previewBytes: ByteArray) : MascotImportState
    data class Downloading(val manifest: MascotImportManifest, val completed: Int, val total: Int) : MascotImportState
    data class Verifying(val manifest: MascotImportManifest) : MascotImportState
    data class Installing(val manifest: MascotImportManifest) : MascotImportState
    data class Installed(val manifest: MascotImportManifest, val packageKey: String) : MascotImportState
    data class AlreadyInstalled(val manifest: MascotImportManifest) : MascotImportState
    data class DownloadFailed(val role: MascotPoseRole) : MascotImportState
    data class IntegrityFailed(val role: MascotPoseRole) : MascotImportState
    data object InstallFailed : MascotImportState
}

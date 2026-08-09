package com.pguillen.gru.mascot.importing

fun interface MascotCodeResolver {
    suspend fun resolve(code: MascotImportCode): MascotResolveResult
}

sealed interface MascotResolveResult {
    data class Found(val manifest: MascotImportManifest) : MascotResolveResult
    data object NotConfigured : MascotResolveResult
    data object NotFound : MascotResolveResult
    data object AccessDenied : MascotResolveResult
    data object NetworkUnavailable : MascotResolveResult
    data class Failed(val errorCode: String) : MascotResolveResult
}

/** Production stays honest until the Web resolver endpoint is configured in a future release. */
object UnavailableMascotCodeResolver : MascotCodeResolver {
    override suspend fun resolve(code: MascotImportCode): MascotResolveResult = MascotResolveResult.NotConfigured
}

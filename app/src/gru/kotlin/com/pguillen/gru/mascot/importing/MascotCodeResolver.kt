package com.pguillen.gru.mascot.importing

import com.pguillen.gru.BuildConfig
import java.io.IOException
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.HttpUrl
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull
import okhttp3.OkHttpClient
import okhttp3.Request

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

/** Resolves only the public, schema-v1 package endpoint configured at build time. */
class HttpMascotCodeResolver(
    baseUrl: String,
    client: OkHttpClient = defaultImportHttpClient(),
) : MascotCodeResolver {
    private val baseUrl = baseUrl.toTrustedImportBaseUrl()
    private val client = client.newBuilder().followRedirects(false).followSslRedirects(false).build()

    override suspend fun resolve(code: MascotImportCode): MascotResolveResult = withContext(Dispatchers.IO) {
        val endpoint = baseUrl ?: return@withContext MascotResolveResult.NotConfigured
        try {
            client.newCall(Request.Builder().url(endpoint.newBuilder().addPathSegments("api/mascot/import").addPathSegment(code.value).build()).get().build())
                .execute().use { response ->
                    if (response.isRedirect) return@withContext MascotResolveResult.Failed("UNSAFE_REDIRECT")
                    when (response.code) {
                        200 -> when (val parsed = MascotImportManifestParser.parse(response.body.readBoundedUtf8())) {
                            is MascotManifestParseResult.Valid -> MascotResolveResult.Found(parsed.manifest)
                            is MascotManifestParseResult.Invalid -> MascotResolveResult.Failed("INVALID_MANIFEST_${parsed.reason.name}")
                            MascotManifestParseResult.Malformed -> MascotResolveResult.Failed("MALFORMED_MANIFEST")
                        }
                        401, 403 -> MascotResolveResult.AccessDenied
                        404 -> MascotResolveResult.NotFound
                        else -> MascotResolveResult.Failed("HTTP_${response.code}")
                    }
                }
        } catch (error: MascotManifestResponseException) {
            MascotResolveResult.Failed(error.code)
        } catch (_: IOException) {
            MascotResolveResult.NetworkUnavailable
        }
    }
}

fun mascotCodeResolverFromBuildConfig(): MascotCodeResolver =
    if (BuildConfig.MASCOT_IMPORT_BASE_URL.isBlank()) UnavailableMascotCodeResolver
    else HttpMascotCodeResolver(BuildConfig.MASCOT_IMPORT_BASE_URL)

private fun String.toTrustedImportBaseUrl(): HttpUrl? = trim().trimEnd('/').toHttpUrlOrNull()?.takeIf { url ->
    url.scheme == "https" && url.username.isEmpty() && url.password.isEmpty() &&
        url.port in setOf(443, -1) && !url.host.isLocalOrPrivateHost()
}

private fun defaultImportHttpClient() = OkHttpClient.Builder()
    .connectTimeout(8, TimeUnit.SECONDS)
    .readTimeout(12, TimeUnit.SECONDS)
    .callTimeout(15, TimeUnit.SECONDS)
    .build()

private fun okhttp3.ResponseBody.readBoundedUtf8(): String {
    if (contentLength() > MascotImportManifest.MAX_MANIFEST_BYTES) throw MascotManifestResponseException("MANIFEST_TOO_LARGE")
    byteStream().use { input ->
        val output = java.io.ByteArrayOutputStream()
        val buffer = ByteArray(DEFAULT_BUFFER_SIZE)
        while (true) {
            val count = input.read(buffer)
            if (count < 0) break
            if (output.size() + count > MascotImportManifest.MAX_MANIFEST_BYTES) throw MascotManifestResponseException("MANIFEST_TOO_LARGE")
            output.write(buffer, 0, count)
        }
        return output.toString(Charsets.UTF_8.name())
    }
}

private class MascotManifestResponseException(val code: String) : IOException(code)

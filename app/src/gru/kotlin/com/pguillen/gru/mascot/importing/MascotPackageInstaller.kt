package com.pguillen.gru.mascot.importing

import android.graphics.BitmapFactory
import com.pguillen.gru.mascot.CustomMascotStore
import java.io.IOException
import java.security.MessageDigest
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.HttpUrl
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull

fun interface MascotAssetDownloader {
    suspend fun download(asset: MascotImportAsset): ByteArray
}

fun interface MascotAssetUrlPolicy {
    fun allows(url: HttpUrl): Boolean

    companion object {
        val SAFE_PUBLIC_HTTPS = MascotAssetUrlPolicy { url -> url.toString().isSafeHttpsAssetUrl() }
    }
}

class HttpMascotAssetDownloader(
    client: OkHttpClient = OkHttpClient(),
    private val urlPolicy: MascotAssetUrlPolicy = MascotAssetUrlPolicy.SAFE_PUBLIC_HTTPS,
) : MascotAssetDownloader {
    private val client = client.newBuilder().followRedirects(false).followSslRedirects(false).build()

    override suspend fun download(asset: MascotImportAsset): ByteArray = withContext(Dispatchers.IO) {
        var url = asset.assetUrl.toHttpUrlOrNull() ?: throw MascotDownloadException("INVALID_URL")
        repeat(MAX_REDIRECTS + 1) { redirectCount ->
            if (!urlPolicy.allows(url)) throw MascotDownloadException("URL_NOT_ALLOWED")
            client.newCall(Request.Builder().url(url).get().build()).execute().use { response ->
                if (response.isRedirect) {
                    if (redirectCount == MAX_REDIRECTS) throw MascotDownloadException("TOO_MANY_REDIRECTS")
                    url = response.header("Location")?.let(url::resolve) ?: throw MascotDownloadException("INVALID_REDIRECT")
                } else {
                    if (!response.isSuccessful) throw MascotDownloadException("HTTP_${response.code}")
                    val receivedMime = response.body.contentType()?.toString()?.substringBefore(';')?.lowercase()
                    if (receivedMime != asset.mimeType.lowercase()) throw MascotDownloadException("INVALID_MIME")
                    val contentLength = response.body.contentLength()
                    if (contentLength > MascotImportManifest.MAX_ASSET_BYTES) throw MascotDownloadException("FILE_TOO_LARGE")
                    if (contentLength >= 0 && contentLength != asset.expectedBytes) throw MascotDownloadException("INVALID_SIZE")
                    return@withContext response.body.byteStream().use { input ->
                        val output = java.io.ByteArrayOutputStream()
                        val buffer = ByteArray(DEFAULT_BUFFER_SIZE)
                        while (true) {
                            val count = input.read(buffer)
                            if (count < 0) break
                            if (output.size() + count > MascotImportManifest.MAX_ASSET_BYTES) throw MascotDownloadException("FILE_TOO_LARGE")
                            output.write(buffer, 0, count)
                        }
                        output.toByteArray()
                    }
                }
            }
        }
        throw MascotDownloadException("TOO_MANY_REDIRECTS")
    }

    private companion object { const val MAX_REDIRECTS = 3 }
}

fun interface MascotImageInspector { fun dimensions(bytes: ByteArray): Pair<Int, Int>? }

class AndroidMascotImageInspector : MascotImageInspector {
    override fun dimensions(bytes: ByteArray): Pair<Int, Int>? {
        val options = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        BitmapFactory.decodeByteArray(bytes, 0, bytes.size, options)
        return if (options.outWidth > 0 && options.outHeight > 0) options.outWidth to options.outHeight else null
    }
}

class MascotAssetVerifier(private val imageInspector: MascotImageInspector = AndroidMascotImageInspector()) {
    fun verify(asset: MascotImportAsset, bytes: ByteArray): VerificationResult {
        if (asset.mimeType.lowercase() !in MascotImportManifest.ALLOWED_MIME_TYPES) return VerificationResult.INVALID_MIME
        if (bytes.size.toLong() != asset.expectedBytes) return VerificationResult.INVALID_SIZE
        val digest = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }
        if (!digest.equals(asset.sha256, ignoreCase = true)) return VerificationResult.INVALID_CHECKSUM
        val dimensions = imageInspector.dimensions(bytes) ?: return VerificationResult.INVALID_IMAGE
        if (dimensions.first > MAX_IMAGE_DIMENSION || dimensions.second > MAX_IMAGE_DIMENSION ||
            dimensions.first.toLong() * dimensions.second > MAX_IMAGE_PIXELS
        ) return VerificationResult.INVALID_DIMENSIONS
        if (asset.width != null && asset.width != dimensions.first) return VerificationResult.INVALID_DIMENSIONS
        if (asset.height != null && asset.height != dimensions.second) return VerificationResult.INVALID_DIMENSIONS
        return VerificationResult.OK
    }

    private companion object {
        const val MAX_IMAGE_DIMENSION = 4096
        const val MAX_IMAGE_PIXELS = 4_194_304L
    }
}

enum class VerificationResult { OK, INVALID_MIME, INVALID_SIZE, INVALID_CHECKSUM, INVALID_IMAGE, INVALID_DIMENSIONS }

class MascotPackageInstaller(
    private val store: CustomMascotStore,
    private val downloader: MascotAssetDownloader,
    private val verifier: MascotAssetVerifier = MascotAssetVerifier(),
) {
    suspend fun install(
        manifest: MascotImportManifest,
        preloaded: Map<MascotPoseRole, ByteArray> = emptyMap(),
        onProgress: (Int, Int) -> Unit = { _, _ -> },
        onPhase: (MascotInstallPhase) -> Unit = {},
    ): MascotInstallResult {
        manifest.validate()?.let { return MascotInstallResult.InvalidManifest(it) }
        if (store.isImportedPackageInstalled(manifest.mascotId, manifest.packageVersion, manifest.poses.map { it.sha256 })) {
            return MascotInstallResult.AlreadyInstalled(manifest.packageKey())
        }
        val assets = manifest.poses.associate { asset ->
            val bytes = preloaded[asset.role] ?: try { downloader.download(asset) } catch (_: IOException) {
                return MascotInstallResult.DownloadFailed(asset.role)
            } catch (_: IllegalArgumentException) {
                return MascotInstallResult.DownloadFailed(asset.role)
            }
            onPhase(MascotInstallPhase.VERIFYING)
            val verification = withContext(Dispatchers.Default) { verifier.verify(asset, bytes) }
            if (verification != VerificationResult.OK) return MascotInstallResult.IntegrityFailed(asset.role, verification)
            onProgress(manifest.poses.indexOf(asset) + 1, manifest.poses.size)
            asset.role to bytes
        }
        onPhase(MascotInstallPhase.INSTALLING)
        return if (withContext(Dispatchers.IO) { store.promoteImported(manifest, assets) }) {
            MascotInstallResult.Installed(manifest.packageKey())
        } else MascotInstallResult.InstallFailed
    }
}

enum class MascotInstallPhase { VERIFYING, INSTALLING }

sealed interface MascotInstallResult {
    data class Installed(val packageKey: String) : MascotInstallResult
    data class AlreadyInstalled(val packageKey: String) : MascotInstallResult
    data class InvalidManifest(val reason: ManifestValidationError) : MascotInstallResult
    data class DownloadFailed(val role: MascotPoseRole) : MascotInstallResult
    data class IntegrityFailed(val role: MascotPoseRole, val reason: VerificationResult) : MascotInstallResult
    data object InstallFailed : MascotInstallResult
}

class MascotDownloadException(code: String) : IOException(code)

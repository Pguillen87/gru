package com.pguillen.gru.mascot.importing

import java.net.URI
import java.security.MessageDigest
import java.util.Locale

@JvmInline
value class MascotImportCode private constructor(val value: String) {
    companion object {
        private val VALID = Regex("^[A-Z0-9][A-Z0-9-]{4,46}[A-Z0-9]$")

        fun parse(raw: String): MascotImportCode? {
            val normalized = raw.trim().uppercase(Locale.ROOT).replace(Regex("\\s+"), "")
            return normalized.takeIf(VALID::matches)?.let(::MascotImportCode)
        }
    }
}

enum class MascotVisibility { PUBLIC, PRIVATE }
enum class MascotPoseRole { NORMAL, LISTENING, TRANSCRIBING }

data class MascotImportAsset(
    val poseId: String,
    val role: MascotPoseRole,
    val assetUrl: String,
    val sha256: String,
    val expectedBytes: Long,
    val mimeType: String,
    val width: Int? = null,
    val height: Int? = null,
)

data class MascotImportManifest(
    val schemaVersion: Int,
    val mascotId: String,
    val packageVersion: String,
    val displayName: String,
    val visibility: MascotVisibility,
    val preview: MascotImportAsset,
    val poses: List<MascotImportAsset>,
    val metadata: Map<String, String> = emptyMap(),
) {
    fun validate(): ManifestValidationError? {
        if (schemaVersion != SUPPORTED_SCHEMA_VERSION) return ManifestValidationError.UNSUPPORTED_SCHEMA
        if (!mascotId.matches(SAFE_ID) || !packageVersion.matches(SAFE_VERSION)) return ManifestValidationError.INVALID_IDENTITY
        if (displayName.isBlank() || displayName.length > MAX_DISPLAY_NAME_LENGTH) return ManifestValidationError.INVALID_IDENTITY
        if (metadata.size > MAX_METADATA_ENTRIES || metadata.any { (key, value) -> key.length > 32 || value.length > 128 }) {
            return ManifestValidationError.INVALID_METADATA
        }
        if (poses.size != MascotPoseRole.entries.size) return ManifestValidationError.MISSING_POSE
        if (poses.map(MascotImportAsset::role).toSet() != MascotPoseRole.entries.toSet()) return ManifestValidationError.DUPLICATE_OR_MISSING_POSE
        if (poses.map(MascotImportAsset::poseId).distinct().size != poses.size) return ManifestValidationError.DUPLICATE_OR_MISSING_POSE
        val normal = poses.single { it.role == MascotPoseRole.NORMAL }
        if (preview.role != MascotPoseRole.NORMAL || preview.sha256 != normal.sha256 || preview.assetUrl != normal.assetUrl) {
            return ManifestValidationError.INVALID_ASSET
        }
        return (poses + preview).firstNotNullOfOrNull(::validateAsset)
    }

    fun packageKey(): String {
        val identity = "$mascotId\u0000$packageVersion".toByteArray(Charsets.UTF_8)
        val digest = MessageDigest.getInstance("SHA-256").digest(identity).joinToString("") { "%02x".format(it) }
        return "import_${digest.take(40)}"
    }

    private fun validateAsset(asset: MascotImportAsset): ManifestValidationError? = when {
        !asset.poseId.matches(SAFE_ID) -> ManifestValidationError.INVALID_ASSET
        !asset.assetUrl.isSafeHttpsAssetUrl() -> ManifestValidationError.INVALID_ASSET
        asset.sha256.length != 64 || !asset.sha256.all(Char::isHexDigit) -> ManifestValidationError.INVALID_ASSET
        asset.expectedBytes !in 1..MAX_ASSET_BYTES -> ManifestValidationError.FILE_TOO_LARGE
        asset.mimeType.lowercase() !in ALLOWED_MIME_TYPES -> ManifestValidationError.INVALID_MIME
        else -> null
    }

    companion object {
        const val SUPPORTED_SCHEMA_VERSION = 1
        const val MAX_ASSET_BYTES = 8L * 1024L * 1024L
        const val MAX_DISPLAY_NAME_LENGTH = 32
        const val MAX_MANIFEST_BYTES = 64 * 1024
        const val MAX_ASSET_URL_LENGTH = 2_048
        const val MAX_METADATA_ENTRIES = 16
        val ALLOWED_MIME_TYPES = setOf("image/png", "image/jpeg", "image/webp")
        private val SAFE_ID = Regex("^[A-Za-z0-9_-]{1,64}$")
        private val SAFE_VERSION = Regex("^[A-Za-z0-9._-]{1,32}$")
    }
}

enum class ManifestValidationError {
    UNSUPPORTED_SCHEMA, INVALID_IDENTITY, MISSING_POSE, DUPLICATE_OR_MISSING_POSE,
    INVALID_ASSET, INVALID_MIME, INVALID_METADATA, FILE_TOO_LARGE,
}

private fun Char.isHexDigit(): Boolean = this in '0'..'9' || lowercaseChar() in 'a'..'f'

internal fun String.isSafeHttpsAssetUrl(): Boolean = runCatching {
    if (length > MascotImportManifest.MAX_ASSET_URL_LENGTH) return false
    val uri = URI(this)
    val host = uri.host?.lowercase(Locale.ROOT) ?: return false
    uri.scheme.equals("https", ignoreCase = true) && uri.userInfo == null && uri.fragment == null &&
        uri.port in setOf(-1, 443) && !host.isLocalOrPrivateHost()
}.getOrDefault(false)

private fun String.isLocalOrPrivateHost(): Boolean =
    this == "localhost" || this.endsWith(".localhost") || this == "::1" ||
        startsWith("127.") || startsWith("10.") || startsWith("192.168.") ||
        Regex("^172\\.(1[6-9]|2[0-9]|3[01])\\.").containsMatchIn(this) ||
        startsWith("169.254.") || startsWith("0.") || startsWith("fc") || startsWith("fd") || startsWith("fe80:")

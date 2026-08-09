package com.pguillen.gru.mascot.importing

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.intOrNull
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.longOrNull

object MascotImportManifestParser {
    fun parse(raw: String): MascotManifestParseResult = runCatching {
        require(raw.toByteArray(Charsets.UTF_8).size <= MascotImportManifest.MAX_MANIFEST_BYTES)
        val root = Json.parseToJsonElement(raw).jsonObject
        val manifest = MascotImportManifest(
            schemaVersion = root.requiredInt("schemaVersion"),
            mascotId = root.requiredString("mascotId"),
            packageVersion = root.requiredString("packageVersion"),
            displayName = root.requiredString("displayName"),
            visibility = MascotVisibility.valueOf(root.requiredString("visibility")),
            preview = root.requiredObject("preview").toAsset(),
            poses = root["poses"]?.jsonArray?.map { it.jsonObject.toAsset() } ?: error("poses missing"),
            metadata = root["metadata"]?.jsonObject?.mapValues { it.value.jsonPrimitive.content }.orEmpty(),
        )
        manifest.validate()?.let { MascotManifestParseResult.Invalid(it) }
            ?: MascotManifestParseResult.Valid(manifest)
    }.getOrElse { MascotManifestParseResult.Malformed }

    private fun JsonObject.toAsset() = MascotImportAsset(
        poseId = requiredString("poseId"),
        role = MascotPoseRole.valueOf(requiredString("role")),
        assetUrl = requiredString("assetUrl"),
        sha256 = requiredString("sha256"),
        expectedBytes = requiredLong("expectedBytes"),
        mimeType = requiredString("mimeType"),
        width = this["width"]?.jsonPrimitive?.intOrNull,
        height = this["height"]?.jsonPrimitive?.intOrNull,
    )

    private fun JsonObject.requiredString(key: String) = this[key]?.jsonPrimitive?.contentOrNull ?: error("$key missing")
    private fun JsonObject.requiredInt(key: String) = this[key]?.jsonPrimitive?.intOrNull ?: error("$key missing")
    private fun JsonObject.requiredLong(key: String) = this[key]?.jsonPrimitive?.longOrNull ?: error("$key missing")
    private fun JsonObject.requiredObject(key: String) = this[key]?.jsonObject ?: error("$key missing")
}

sealed interface MascotManifestParseResult {
    data class Valid(val manifest: MascotImportManifest) : MascotManifestParseResult
    data class Invalid(val reason: ManifestValidationError) : MascotManifestParseResult
    data object Malformed : MascotManifestParseResult
}

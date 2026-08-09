package com.pguillen.gru.mascot

import android.content.Context
import java.io.File
import java.security.MessageDigest
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonArray
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.longOrNull
import com.pguillen.gru.mascot.importing.MascotImportManifest
import com.pguillen.gru.mascot.importing.MascotImportAsset
import com.pguillen.gru.mascot.importing.MascotPoseRole

/** Private, atomic persistence for approved Masters and completed pose sets. */
class CustomMascotStore internal constructor(private val root: File) {
    constructor(context: Context) : this(File(context.filesDir, "mascots"))

    fun poseFile(poseSetId: String, state: MascotRuntimeState): File? {
        val manifest = read(poseSetId) ?: return null
        val poseId = when (state) {
            MascotRuntimeState.IDLE -> manifest.selectedIdlePoseId
            MascotRuntimeState.RECORDING -> manifest.selectedRecordingPoseId
            MascotRuntimeState.TRANSCRIBING -> manifest.selectedTranscribingPoseId
        }
        return manifest.poses.firstOrNull { it.poseId == poseId }?.let { pose ->
            File(directory(poseSetId), pose.fileName).takeIf { file -> file.isFile && file.readBytes().matchesSha256(pose.sha256) }
        } ?: validatedMasterFile(manifest)
    }

    fun previewFile(poseSetId: String): File? {
        val manifest = read(poseSetId) ?: return null
        return validatedMasterFile(manifest) ?: poseFile(poseSetId, MascotRuntimeState.IDLE)
    }

    fun entries(): List<CustomMascotEntry> = root.listFiles()
        .orEmpty()
        .filter { it.isDirectory && !it.name.startsWith(".") }
        .mapNotNull { folder ->
            val manifest = read(folder.name) ?: return@mapNotNull null
            val preview = previewFile(manifest.poseSetId) ?: return@mapNotNull null
            CustomMascotEntry(
                manifest.poseSetId,
                manifest.masterId,
                preview.absolutePath,
                manifest.poses.isNotEmpty(),
                maxOf(folder.lastModified(), preview.lastModified()),
                manifest.displayName,
                manifest.importedMascotId,
                manifest.packageVersion,
                manifest.source,
                isFavorite(manifest.poseSetId),
                manifest.installedAtMillis,
            )
        }
        .sortedWith(compareByDescending<CustomMascotEntry> { it.favorite }.thenByDescending { it.updatedAtMillis })

    fun read(poseSetId: String): CustomMascotManifest? = runCatching {
        val json = Json.parseToJsonElement(File(directory(poseSetId), MANIFEST).readText()).jsonObject
        val poses = json["poses"]?.jsonArray?.toPoses().orEmpty()
        CustomMascotManifest(
            poseSetId = json.requiredString("poseSetId"), masterId = json.requiredString("masterId"),
            version = json.requiredString("version"), modelVersion = json.string("modelVersion")?.ifBlank { null },
            poses = poses, selectedIdlePoseId = json.string("idle").orEmpty(),
            selectedRecordingPoseId = json.string("recording").orEmpty(), selectedTranscribingPoseId = json.string("transcribing").orEmpty(),
            masterFileName = json.string("masterFileName")?.ifBlank { null },
            masterSha256 = json.string("masterSha256")?.ifBlank { null },
            displayName = json.string("displayName")?.ifBlank { null },
            importedMascotId = json.string("importedMascotId")?.ifBlank { null },
            packageVersion = json.string("packageVersion")?.ifBlank { null },
            source = json.string("source")?.ifBlank { null } ?: "legacy_custom",
            favorite = json["favorite"]?.jsonPrimitive?.booleanOrNull ?: false,
            installedAtMillis = json["installedAtMillis"]?.jsonPrimitive?.longOrNull ?: 0L,
        )
    }.getOrNull()

    fun promoteMaster(poseSetId: String, masterId: String, image: ByteArray): Boolean {
        val checksum = image.sha256()
        val manifest = CustomMascotManifest(
            poseSetId = poseSetId,
            masterId = masterId,
            version = "master-v1",
            modelVersion = null,
            poses = emptyList(),
            selectedIdlePoseId = "",
            selectedRecordingPoseId = "",
            selectedTranscribingPoseId = "",
            masterFileName = MASTER,
            masterSha256 = checksum,
        )
        return promoteFiles(manifest, mapOf(MASTER to image))
    }

    fun promote(manifest: CustomMascotManifest, images: Map<String, ByteArray>): Boolean = runCatching {
        require(manifest.isSafe())
        require(manifest.poses.all { pose -> images[pose.poseId]?.matchesSha256(pose.sha256) == true })
        val files = manifest.poses.associate { pose -> pose.fileName to images.getValue(pose.poseId) }
        promoteFiles(manifest, files)
    }.getOrElse { false }

    fun rename(poseSetId: String, name: String): Boolean {
        val normalized = normalizeDisplayName(name)
        if (normalized.isBlank()) return false
        val manifest = read(poseSetId) ?: return false
        val folder = directory(poseSetId)
        val files = buildMap {
            manifest.masterFileName?.let { fileName -> put(fileName, File(folder, fileName).readBytes()) }
            manifest.poses.forEach { pose -> put(pose.fileName, File(folder, pose.fileName).readBytes()) }
        }
        return promoteFiles(manifest.copy(displayName = normalized), files)
    }

    fun setFavorite(poseSetId: String, favorite: Boolean): Boolean {
        if (read(poseSetId) == null) return false
        return runCatching {
            val marker = File(directory(poseSetId), FAVORITE)
            if (favorite) marker.writeText("1") else if (marker.exists()) check(marker.delete())
            true
        }.getOrDefault(false)
    }

    private fun isFavorite(poseSetId: String): Boolean = File(directory(poseSetId), FAVORITE).isFile

    fun isImportedPackageInstalled(mascotId: String, packageVersion: String, checksums: List<String>): Boolean =
        entries().any { entry ->
            if (entry.importedMascotId != mascotId || entry.packageVersion != packageVersion) return@any false
            val manifest = read(entry.poseSetId) ?: return@any false
            manifest.poses.map(MascotPose::sha256).toSet() == checksums.toSet()
        }

    fun promoteImported(manifest: MascotImportManifest, images: Map<MascotPoseRole, ByteArray>): Boolean {
        if (manifest.validate() != null || images.keys != MascotPoseRole.entries.toSet()) return false
        val packageKey = manifest.packageKey()
        val poses = manifest.poses.map { asset ->
            val extension = when (asset.mimeType.lowercase()) {
                "image/png" -> "png"
                "image/jpeg" -> "jpg"
                else -> "webp"
            }
            val fileName = "${asset.role.name.lowercase()}.$extension"
            MascotPose(asset.poseId, asset.role.name, fileName, asset.sha256)
        }
        val byRole = manifest.poses.associateBy(MascotImportAsset::role)
        val local = CustomMascotManifest(
            poseSetId = packageKey,
            masterId = manifest.mascotId,
            version = manifest.packageVersion,
            modelVersion = null,
            poses = poses,
            selectedIdlePoseId = requireNotNull(byRole[MascotPoseRole.NORMAL]).poseId,
            selectedRecordingPoseId = requireNotNull(byRole[MascotPoseRole.LISTENING]).poseId,
            selectedTranscribingPoseId = requireNotNull(byRole[MascotPoseRole.TRANSCRIBING]).poseId,
            displayName = normalizeDisplayName(manifest.displayName),
            importedMascotId = manifest.mascotId,
            packageVersion = manifest.packageVersion,
            source = "code_import",
            installedAtMillis = System.currentTimeMillis(),
        )
        val bytes = manifest.poses.associate { asset -> asset.poseId to images.getValue(asset.role) }
        return promote(local, bytes)
    }

    private fun rewrite(manifest: CustomMascotManifest): Boolean {
        val folder = directory(manifest.poseSetId)
        val files = buildMap {
            manifest.masterFileName?.let { fileName -> put(fileName, File(folder, fileName).readBytes()) }
            manifest.poses.forEach { pose -> put(pose.fileName, File(folder, pose.fileName).readBytes()) }
        }
        return promoteFiles(manifest, files)
    }

    private fun promoteFiles(manifest: CustomMascotManifest, files: Map<String, ByteArray>): Boolean = runCatching {
        require(manifest.isSafe())
        root.mkdirs()
        val staging = File(root, ".${manifest.poseSetId}.staging")
        staging.deleteRecursively(); staging.mkdirs()
        files.forEach { (name, bytes) -> File(staging, name).writeBytes(bytes) }
        File(staging, MANIFEST).writeText(Json.encodeToString(JsonObject.serializer(), manifest.toJson()))
        val target = directory(manifest.poseSetId)
        val backup = File(root, ".${manifest.poseSetId}.backup")
        backup.deleteRecursively()
        if (target.exists()) check(target.renameTo(backup))
        if (!staging.renameTo(target)) {
            if (backup.exists()) check(backup.renameTo(target))
            error("Unable to promote mascot package.")
        }
        backup.deleteRecursively()
        true
    }.getOrElse { false }

    fun remove(poseSetId: String): Boolean = runCatching { directory(poseSetId).deleteRecursively() }.getOrDefault(false)

    private fun directory(poseSetId: String): File {
        require(poseSetId.matches(Regex("^[A-Za-z0-9_-]{1,96}$")))
        return File(root, poseSetId)
    }

    private fun JsonArray.toPoses() = map { element -> element.jsonObject.let {
        MascotPose(
            it.requiredString("poseId"), it.requiredString("name"), it.requiredString("fileName"),
            it.requiredString("sha256"), it.string("downloadPath")?.ifBlank { null },
        )
    } }

    private fun CustomMascotManifest.toJson() = buildJsonObject {
        put("poseSetId", JsonPrimitive(poseSetId)); put("masterId", JsonPrimitive(masterId)); put("version", JsonPrimitive(version))
        put("modelVersion", JsonPrimitive(modelVersion ?: "")); put("idle", JsonPrimitive(selectedIdlePoseId))
        put("recording", JsonPrimitive(selectedRecordingPoseId)); put("transcribing", JsonPrimitive(selectedTranscribingPoseId))
        put("masterFileName", JsonPrimitive(masterFileName ?: "")); put("masterSha256", JsonPrimitive(masterSha256 ?: ""))
        put("displayName", JsonPrimitive(displayName ?: ""))
        put("importedMascotId", JsonPrimitive(importedMascotId ?: "")); put("packageVersion", JsonPrimitive(packageVersion ?: ""))
        put("source", JsonPrimitive(source)); put("favorite", JsonPrimitive(favorite)); put("installedAtMillis", JsonPrimitive(installedAtMillis))
        put("poses", buildJsonArray { poses.forEach { pose -> add(buildJsonObject {
            put("poseId", JsonPrimitive(pose.poseId)); put("name", JsonPrimitive(pose.name)); put("fileName", JsonPrimitive(pose.fileName))
            put("sha256", JsonPrimitive(pose.sha256)); put("downloadPath", JsonPrimitive(pose.downloadPath ?: ""))
        }) } })
    }

    private fun validatedMasterFile(manifest: CustomMascotManifest): File? {
        val name = manifest.masterFileName ?: return null
        val checksum = manifest.masterSha256 ?: return null
        return File(directory(manifest.poseSetId), name)
            .takeIf { file -> file.isFile && file.readBytes().matchesSha256(checksum) }
    }

    companion object {
        private const val MANIFEST = "manifest.json"
        private const val MASTER = "master.png"
        private const val FAVORITE = ".favorite"
        const val MAX_DISPLAY_NAME_LENGTH = 32
    }
}

internal fun normalizeDisplayName(value: String): String =
    value.trim().replace(Regex("\\s+"), " ").take(CustomMascotStore.MAX_DISPLAY_NAME_LENGTH)

private fun CustomMascotManifest.isSafe(): Boolean {
    val poseIds = poses.map(MascotPose::poseId)
    val filenames = poses.map(MascotPose::fileName)
    val safeIdentity = poseSetId.matches(Regex("^[A-Za-z0-9_-]{1,96}$")) && masterId.matches(Regex("^[A-Za-z0-9_-]{1,96}$"))
    val safeMaster = masterFileName?.let { File(it).name == it } == true && masterSha256?.matches(Regex("^[a-fA-F0-9]{64}$")) == true
    val safePoses = poses.isNotEmpty() &&
        poseIds.size == poseIds.toSet().size && filenames.size == filenames.toSet().size &&
        poses.all { pose ->
            pose.poseId.matches(Regex("^[A-Za-z0-9_-]{1,64}$")) && File(pose.fileName).name == pose.fileName
        } && listOf(selectedIdlePoseId, selectedRecordingPoseId, selectedTranscribingPoseId).all(poseIds::contains)
    return safeIdentity && (safeMaster || safePoses)
}

internal fun ByteArray.matchesSha256(expected: String): Boolean = MessageDigest.getInstance("SHA-256")
    .digest(this).joinToString("") { "%02x".format(it) } == expected.lowercase()

private fun ByteArray.sha256(): String = MessageDigest.getInstance("SHA-256")
    .digest(this).joinToString("") { "%02x".format(it) }

private fun JsonObject.string(key: String): String? = this[key]?.jsonPrimitive?.content
private fun JsonObject.requiredString(key: String): String = requireNotNull(string(key))

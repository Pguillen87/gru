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
            )
        }
        .sortedBy(CustomMascotEntry::updatedAtMillis)

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

    private companion object {
        const val MANIFEST = "manifest.json"
        const val MASTER = "master.png"
    }
}

private fun CustomMascotManifest.isSafe(): Boolean {
    val poseIds = poses.map(MascotPose::poseId)
    val filenames = poses.map(MascotPose::fileName)
    val safeIdentity = poseSetId.matches(Regex("^[A-Za-z0-9_-]{1,96}$")) && masterId.matches(Regex("^master_[1-4]$"))
    val safeMaster = masterFileName?.let { File(it).name == it } == true && masterSha256?.matches(Regex("^[a-fA-F0-9]{64}$")) == true
    val safePoses = poses.isNotEmpty() &&
        poseIds.size == poseIds.toSet().size && filenames.size == filenames.toSet().size &&
        poses.all { pose ->
            pose.poseId.matches(Regex("^pose_[0-9]{2}$")) && File(pose.fileName).name == pose.fileName
        } && listOf(selectedIdlePoseId, selectedRecordingPoseId, selectedTranscribingPoseId).all(poseIds::contains)
    return safeIdentity && (safeMaster || safePoses)
}

internal fun ByteArray.matchesSha256(expected: String): Boolean = MessageDigest.getInstance("SHA-256")
    .digest(this).joinToString("") { "%02x".format(it) } == expected.lowercase()

private fun ByteArray.sha256(): String = MessageDigest.getInstance("SHA-256")
    .digest(this).joinToString("") { "%02x".format(it) }

private fun JsonObject.string(key: String): String? = this[key]?.jsonPrimitive?.content
private fun JsonObject.requiredString(key: String): String = requireNotNull(string(key))

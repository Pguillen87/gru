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

/** Private, atomic persistence for a completed pose set. */
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
        }
    }

    fun read(poseSetId: String): CustomMascotManifest? = runCatching {
        val json = Json.parseToJsonElement(File(directory(poseSetId), MANIFEST).readText()).jsonObject
        val poses = json.getValue("poses").jsonArray.toPoses()
        CustomMascotManifest(
            poseSetId = json.requiredString("poseSetId"), masterId = json.requiredString("masterId"),
            version = json.requiredString("version"), modelVersion = json.string("modelVersion")?.ifBlank { null },
            poses = poses, selectedIdlePoseId = json.requiredString("idle"),
            selectedRecordingPoseId = json.requiredString("recording"), selectedTranscribingPoseId = json.requiredString("transcribing"),
        )
    }.getOrNull()

    fun promote(manifest: CustomMascotManifest, images: Map<String, ByteArray>): Boolean = runCatching {
        require(manifest.isSafe())
        require(manifest.poses.all { pose -> images[pose.poseId]?.matchesSha256(pose.sha256) == true })
        root.mkdirs()
        val staging = File(root, ".${manifest.poseSetId}.staging")
        staging.deleteRecursively(); staging.mkdirs()
        manifest.poses.forEach { pose -> File(staging, pose.fileName).writeBytes(images.getValue(pose.poseId)) }
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
        put("poses", buildJsonArray { poses.forEach { pose -> add(buildJsonObject {
            put("poseId", JsonPrimitive(pose.poseId)); put("name", JsonPrimitive(pose.name)); put("fileName", JsonPrimitive(pose.fileName))
            put("sha256", JsonPrimitive(pose.sha256)); put("downloadPath", JsonPrimitive(pose.downloadPath ?: ""))
        }) } })
    }

    private companion object { const val MANIFEST = "manifest.json" }
}

private fun CustomMascotManifest.isSafe(): Boolean {
    val poseIds = poses.map(MascotPose::poseId)
    val filenames = poses.map(MascotPose::fileName)
    return poseSetId.matches(Regex("^[A-Za-z0-9_-]{1,96}$")) &&
        masterId.matches(Regex("^master_[1-4]$")) && poses.isNotEmpty() &&
        poseIds.size == poseIds.toSet().size && filenames.size == filenames.toSet().size &&
        poses.all { pose ->
            pose.poseId.matches(Regex("^pose_[0-9]{2}$")) && File(pose.fileName).name == pose.fileName
        } && listOf(selectedIdlePoseId, selectedRecordingPoseId, selectedTranscribingPoseId).all(poseIds::contains)
}

internal fun ByteArray.matchesSha256(expected: String): Boolean = MessageDigest.getInstance("SHA-256")
    .digest(this).joinToString("") { "%02x".format(it) } == expected.lowercase()

private fun JsonObject.string(key: String): String? = this[key]?.jsonPrimitive?.content
private fun JsonObject.requiredString(key: String): String = requireNotNull(string(key))

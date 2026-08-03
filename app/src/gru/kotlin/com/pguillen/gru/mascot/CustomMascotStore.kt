package com.pguillen.gru.mascot

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.io.File

/** Private, atomic persistence for a completed pose set. */
class CustomMascotStore(context: Context) {
    private val root = File(context.filesDir, "mascots")

    fun poseFile(poseSetId: String, state: MascotRuntimeState): File? {
        val manifest = read(poseSetId) ?: return null
        val poseId = when (state) {
            MascotRuntimeState.IDLE -> manifest.selectedIdlePoseId
            MascotRuntimeState.RECORDING -> manifest.selectedRecordingPoseId
            MascotRuntimeState.TRANSCRIBING -> manifest.selectedTranscribingPoseId
        }
        return manifest.poses.firstOrNull { it.poseId == poseId }?.let { File(directory(poseSetId), it.fileName) }
    }

    fun read(poseSetId: String): CustomMascotManifest? = runCatching {
        val json = JSONObject(File(directory(poseSetId), MANIFEST).readText())
        val poses = json.getJSONArray("poses").toPoses()
        CustomMascotManifest(
            poseSetId = json.getString("poseSetId"), masterId = json.getString("masterId"),
            version = json.getString("version"), modelVersion = json.optString("modelVersion").ifBlank { null },
            poses = poses, selectedIdlePoseId = json.getString("idle"),
            selectedRecordingPoseId = json.getString("recording"), selectedTranscribingPoseId = json.getString("transcribing"),
        )
    }.getOrNull()

    fun promote(manifest: CustomMascotManifest, images: Map<String, ByteArray>): Boolean = runCatching {
        require(manifest.poses.isNotEmpty())
        require(manifest.poses.all { images.containsKey(it.poseId) })
        root.mkdirs()
        val staging = File(root, ".${manifest.poseSetId}.staging")
        staging.deleteRecursively(); staging.mkdirs()
        manifest.poses.forEach { pose -> File(staging, pose.fileName).writeBytes(images.getValue(pose.poseId)) }
        File(staging, MANIFEST).writeText(manifest.toJson().toString())
        val target = directory(manifest.poseSetId)
        val backup = File(root, ".${manifest.poseSetId}.backup")
        backup.deleteRecursively()
        if (target.exists()) target.renameTo(backup)
        check(staging.renameTo(target))
        backup.deleteRecursively()
        true
    }.getOrElse { false }

    fun remove(poseSetId: String) = directory(poseSetId).deleteRecursively()

    private fun directory(poseSetId: String) = File(root, poseSetId)

    private fun JSONArray.toPoses() = List(length()) { index -> getJSONObject(index).let {
        MascotPose(it.getString("poseId"), it.getString("name"), it.getString("fileName"))
    } }

    private fun CustomMascotManifest.toJson() = JSONObject().apply {
        put("poseSetId", poseSetId); put("masterId", masterId); put("version", version)
        put("modelVersion", modelVersion ?: ""); put("idle", selectedIdlePoseId)
        put("recording", selectedRecordingPoseId); put("transcribing", selectedTranscribingPoseId)
        put("poses", JSONArray().apply { poses.forEach { put(JSONObject().apply {
            put("poseId", it.poseId); put("name", it.name); put("fileName", it.fileName)
        }) } })
    }

    private companion object { const val MANIFEST = "manifest.json" }
}

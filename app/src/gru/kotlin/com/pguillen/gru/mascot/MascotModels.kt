package com.pguillen.gru.mascot

import com.pguillen.gru.GruPet

/** Visual source used by the overlay. Custom image bytes always remain on-device. */
sealed interface MascotSource {
    data class BuiltIn(val pet: GruPet) : MascotSource
    data class Custom(val poseSetId: String, val masterId: String) : MascotSource
}

enum class MascotRuntimeState { IDLE, RECORDING, TRANSCRIBING }

data class MascotPose(
    val poseId: String,
    val name: String,
    val fileName: String,
    val sha256: String,
    val downloadPath: String? = null,
)

data class CustomMascotManifest(
    val poseSetId: String,
    val masterId: String,
    val version: String,
    val modelVersion: String?,
    val poses: List<MascotPose>,
    val selectedIdlePoseId: String,
    val selectedRecordingPoseId: String,
    val selectedTranscribingPoseId: String,
    val masterFileName: String? = null,
    val masterSha256: String? = null,
)

data class CustomMascotEntry(
    val poseSetId: String,
    val masterId: String,
    val previewPath: String,
    val hasAuthoredPoses: Boolean,
    val updatedAtMillis: Long,
)

sealed interface MascotVisual {
    data class Atlas(val drawableRes: Int) : MascotVisual
    data class ImageFile(val absolutePath: String) : MascotVisual
}

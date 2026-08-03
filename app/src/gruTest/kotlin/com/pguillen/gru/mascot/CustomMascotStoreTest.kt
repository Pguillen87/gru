package com.pguillen.gru.mascot

import java.nio.file.Files
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertTrue

class CustomMascotStoreTest {
    @Test fun `valid package is promoted and resolves every runtime state`() {
        val root = Files.createTempDirectory("gru-mascot-test").toFile()
        try {
            val store = CustomMascotStore(root)
            val fixture = fixture("set-1", "approved".encodeToByteArray())
            assertTrue(store.promote(fixture.manifest, fixture.images))
            assertNotNull(store.poseFile("set-1", MascotRuntimeState.IDLE))
            assertNotNull(store.poseFile("set-1", MascotRuntimeState.RECORDING))
            assertNotNull(store.poseFile("set-1", MascotRuntimeState.TRANSCRIBING))
        } finally { root.deleteRecursively() }
    }

    @Test fun `corrupt replacement never removes the active package`() {
        val root = Files.createTempDirectory("gru-mascot-test").toFile()
        try {
            val store = CustomMascotStore(root)
            val approved = fixture("set-1", "approved".encodeToByteArray())
            assertTrue(store.promote(approved.manifest, approved.images))
            val corrupt = approved.images.mapValues { "corrupt".encodeToByteArray() }
            assertFalse(store.promote(approved.manifest, corrupt))
            assertEquals("approved", store.poseFile("set-1", MascotRuntimeState.IDLE)?.readText())
        } finally { root.deleteRecursively() }
    }

    @Test fun `path traversal in manifest is rejected`() {
        val root = Files.createTempDirectory("gru-mascot-test").toFile()
        try {
            val store = CustomMascotStore(root)
            val fixture = fixture("set-1", "approved".encodeToByteArray())
            val unsafe = fixture.manifest.copy(poses = fixture.manifest.poses.map { it.copy(fileName = "../escape.png") })
            assertFalse(store.promote(unsafe, fixture.images))
            assertFalse(requireNotNull(root.parentFile).resolve("escape.png").exists())
        } finally { root.deleteRecursively() }
    }

    @Test fun `path traversal cannot remove files outside mascot storage`() {
        val root = Files.createTempDirectory("gru-mascot-test").toFile()
        val marker = requireNotNull(root.parentFile).resolve("keep-me-${root.name}").apply { writeText("safe") }
        try {
            assertFalse(CustomMascotStore(root).remove("../${marker.name}"))
            assertTrue(marker.isFile)
        } finally {
            marker.delete()
            root.deleteRecursively()
        }
    }
}

private data class StoreFixture(val manifest: CustomMascotManifest, val images: Map<String, ByteArray>)

private fun fixture(poseSetId: String, bytes: ByteArray): StoreFixture {
    val checksum = java.security.MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }
    val poses = (1..3).map { index ->
        MascotPose("pose_0$index", "Pose $index", "pose_0$index.png", checksum, "/download/$index")
    }
    return StoreFixture(
        CustomMascotManifest(poseSetId, "master_1", "v1", "model", poses, "pose_01", "pose_02", "pose_03"),
        poses.associate { it.poseId to bytes },
    )
}

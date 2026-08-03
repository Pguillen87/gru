package com.pguillen.gru.mascot

import java.nio.file.Files
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertTrue

class CustomMascotStoreTest {
    @Test fun `approved Master becomes a selectable animated fallback before poses exist`() {
        val root = Files.createTempDirectory("gru-master-test").toFile()
        try {
            val store = CustomMascotStore(root)
            val image = "approved-master".encodeToByteArray()
            assertTrue(store.promoteMaster("job-1", "master_2", image))

            val entry = store.entries().single()
            assertEquals("job-1", entry.poseSetId)
            assertEquals("master_2", entry.masterId)
            assertFalse(entry.hasAuthoredPoses)
            MascotRuntimeState.entries.forEach { state ->
                assertEquals("approved-master", store.poseFile("job-1", state)?.readText())
            }
        } finally { root.deleteRecursively() }
    }

    @Test fun `multiple approved Masters remain in the custom gallery`() {
        val root = Files.createTempDirectory("gru-library-test").toFile()
        try {
            val store = CustomMascotStore(root)
            assertTrue(store.promoteMaster("job-1", "master_1", byteArrayOf(1)))
            assertTrue(store.promoteMaster("job-2", "master_3", byteArrayOf(2)))
            assertEquals(setOf("job-1", "job-2"), store.entries().map { it.poseSetId }.toSet())
        } finally { root.deleteRecursively() }
    }

    @Test fun `custom mascot name is persisted without changing its artwork`() {
        val root = Files.createTempDirectory("gru-name-test").toFile()
        try {
            val store = CustomMascotStore(root)
            assertTrue(store.promoteMaster("job-1", "master_1", "image".encodeToByteArray()))
            assertTrue(store.rename("job-1", "  Luna   Azul  "))

            assertEquals("Luna Azul", store.entries().single().displayName)
            assertEquals("image", store.previewFile("job-1")?.readText())
        } finally { root.deleteRecursively() }
    }

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

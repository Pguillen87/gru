package com.pguillen.gru.mascot

import com.pguillen.gru.mascot.importing.ManifestValidationError
import com.pguillen.gru.mascot.importing.MascotAssetDownloader
import com.pguillen.gru.mascot.importing.MascotAssetVerifier
import com.pguillen.gru.mascot.importing.MascotCodeResolver
import com.pguillen.gru.mascot.importing.MascotImportAsset
import com.pguillen.gru.mascot.importing.MascotImportCode
import com.pguillen.gru.mascot.importing.MascotImportCoordinator
import com.pguillen.gru.mascot.importing.MascotImportManifest
import com.pguillen.gru.mascot.importing.MascotImportState
import com.pguillen.gru.mascot.importing.MascotInstallResult
import com.pguillen.gru.mascot.importing.MascotPackageInstaller
import com.pguillen.gru.mascot.importing.MascotPoseRole
import com.pguillen.gru.mascot.importing.MascotResolveResult
import com.pguillen.gru.mascot.importing.MascotVisibility
import com.pguillen.gru.mascot.importing.MascotImportManifestParser
import com.pguillen.gru.mascot.importing.MascotManifestParseResult
import com.pguillen.gru.mascot.importing.UnavailableMascotCodeResolver
import java.nio.file.Files
import java.security.MessageDigest
import java.util.Locale
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.flow.first
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertIs
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue

class MascotImportTest {
    @Test fun `versioned manifest parser accepts valid payload and rejects malformed payload`() {
        val checksum = BYTES.sha256()
        fun asset(role: String) = """{"poseId":"${role.lowercase()}","role":"$role","assetUrl":"https://assets.example.invalid/${role.lowercase()}.png","sha256":"$checksum","expectedBytes":4,"mimeType":"image/png","width":24,"height":24}"""
        val normal = asset("NORMAL")
        val json = """{"schemaVersion":1,"mascotId":"bob","packageVersion":"v1","displayName":"Bob","visibility":"PUBLIC","preview":$normal,"poses":[$normal,${asset("LISTENING")},${asset("TRANSCRIBING")}],"metadata":{}}"""
        assertIs<MascotManifestParseResult.Valid>(MascotImportManifestParser.parse(json))
        assertIs<MascotManifestParseResult.Malformed>(MascotImportManifestParser.parse("{}"))
    }
    @Test fun `production resolver is honest while no endpoint exists`() = runTest {
        assertIs<MascotResolveResult.NotConfigured>(UnavailableMascotCodeResolver.resolve(assertNotNull(MascotImportCode.parse("BOB-AB12"))))
    }
    @Test fun `code is normalized without coupling to pose numbers`() {
        assertEquals("BOB-AB12", MascotImportCode.parse("  bob-ab12 ")?.value)
        assertNull(MascotImportCode.parse(""))
        assertNull(MascotImportCode.parse("a/b/c"))
    }

    @Test fun `code normalization is stable across locales`() {
        val previous = Locale.getDefault()
        try {
            Locale.setDefault(Locale.forLanguageTag("tr-TR"))
            assertEquals("MINI-123", MascotImportCode.parse("mini-123")?.value)
        } finally {
            Locale.setDefault(previous)
        }
    }

    @Test fun `package key cannot collide after version sanitization`() {
        val first = validManifest().copy(packageVersion = "v1.0").packageKey()
        val second = validManifest().copy(packageVersion = "v1_0").packageKey()
        assertTrue(first != second)
    }

    @Test fun `manifest requires schema one and exactly three unique roles`() {
        assertNull(validManifest().validate())
        assertEquals(ManifestValidationError.UNSUPPORTED_SCHEMA, validManifest().copy(schemaVersion = 2).validate())
        assertEquals(ManifestValidationError.MISSING_POSE, validManifest().copy(poses = validManifest().poses.take(2)).validate())
        val duplicate = validManifest().poses.map { it.copy(role = MascotPoseRole.NORMAL) }
        assertEquals(ManifestValidationError.DUPLICATE_OR_MISSING_POSE, validManifest().copy(poses = duplicate).validate())
    }

    @Test fun `manifest rejects invalid mime and oversized assets`() {
        val invalidMime = validManifest().poses.first().copy(mimeType = "text/html")
        assertEquals(ManifestValidationError.INVALID_MIME, validManifest().copy(poses = listOf(invalidMime) + validManifest().poses.drop(1)).validate())
        val huge = validManifest().poses.first().copy(expectedBytes = MascotImportManifest.MAX_ASSET_BYTES + 1)
        assertEquals(ManifestValidationError.FILE_TOO_LARGE, validManifest().copy(poses = listOf(huge) + validManifest().poses.drop(1)).validate())
        val privateUrl = validManifest().poses.first().copy(assetUrl = "https://127.0.0.1/normal.png")
        assertEquals(ManifestValidationError.INVALID_ASSET, validManifest().copy(preview = privateUrl, poses = listOf(privateUrl) + validManifest().poses.drop(1)).validate())
    }

    @Test fun `fake resolver exposes preview only in tests`() = runTest {
        val store = CustomMascotStore(Files.createTempDirectory("perch-resolve").toFile())
        val coordinator = MascotImportCoordinator(
            resolver = MascotCodeResolver { MascotResolveResult.Found(validManifest()) },
            installer = installer(store),
            store = store,
            previewDownloader = MascotAssetDownloader { BYTES },
            verifier = verifier(),
        )
        coordinator.resolve("BOB-AB12")
        assertIs<MascotImportState.PreviewReady>(coordinator.state.value)
    }

    @Test fun `three verified poses install atomically and map runtime states`() = runTest {
        val root = Files.createTempDirectory("perch-install").toFile()
        val store = CustomMascotStore(root)
        val manifest = validManifest()
        val result = installer(store).install(manifest)
        assertIs<MascotInstallResult.Installed>(result)
        val entry = assertNotNull(store.entries().singleOrNull())
        assertEquals("bob", entry.importedMascotId)
        assertNotNull(store.poseFile(entry.poseSetId, MascotRuntimeState.IDLE))
        assertNotNull(store.poseFile(entry.poseSetId, MascotRuntimeState.RECORDING))
        assertNotNull(store.poseFile(entry.poseSetId, MascotRuntimeState.TRANSCRIBING))
    }

    @Test fun `integrity failure leaves no partial package`() = runTest {
        val root = Files.createTempDirectory("perch-rollback").toFile()
        val store = CustomMascotStore(root)
        val manifest = validManifest()
        val corruptDownloader = MascotAssetDownloader { asset -> if (asset.role == MascotPoseRole.LISTENING) byteArrayOf(9) else BYTES }
        val result = MascotPackageInstaller(store, corruptDownloader, verifier()).install(manifest)
        assertIs<MascotInstallResult.IntegrityFailed>(result)
        assertTrue(store.entries().isEmpty())
    }

    @Test fun `same package is not downloaded twice`() = runTest {
        val store = CustomMascotStore(Files.createTempDirectory("perch-dedupe").toFile())
        val installer = installer(store)
        assertIs<MascotInstallResult.Installed>(installer.install(validManifest()))
        assertIs<MascotInstallResult.AlreadyInstalled>(installer.install(validManifest()))
    }

    @Test fun `favorite metadata changes without touching pose files and removal works`() = runTest {
        val store = CustomMascotStore(Files.createTempDirectory("perch-favorite").toFile())
        val installed = assertIs<MascotInstallResult.Installed>(installer(store).install(validManifest()))
        val idle = assertNotNull(store.poseFile(installed.packageKey, MascotRuntimeState.IDLE))
        val modified = idle.lastModified()
        assertTrue(store.setFavorite(installed.packageKey, true))
        assertTrue(store.entries().single().favorite)
        assertEquals(modified, assertNotNull(store.poseFile(installed.packageKey, MascotRuntimeState.IDLE)).lastModified())
        assertTrue(store.setFavorite(installed.packageKey, false))
        assertFalse(store.entries().single().favorite)
        assertTrue(store.remove(installed.packageKey))
        assertTrue(store.entries().isEmpty())
    }

    @Test fun `manual order persists and favorite does not override it`() = runTest {
        val root = Files.createTempDirectory("perch-order").toFile()
        val store = CustomMascotStore(root)
        val first = validManifest().copy(mascotId = "first", displayName = "First")
        val second = validManifest().copy(mascotId = "second", displayName = "Second")
        val firstKey = assertIs<MascotInstallResult.Installed>(installer(store).install(first)).packageKey
        val secondKey = assertIs<MascotInstallResult.Installed>(installer(store).install(second)).packageKey

        assertEquals(listOf(firstKey, secondKey), store.entries().map { it.poseSetId })
        assertTrue(store.reorderImported(secondKey, -1))
        assertTrue(CustomMascotStore(root).setFavorite(firstKey, true))
        assertEquals(listOf(secondKey, firstKey), CustomMascotStore(root).entries().map { it.poseSetId })
    }

    @Test fun `installation is immediately observable from another store instance`() = runTest {
        val root = Files.createTempDirectory("perch-observe").toFile()
        val installerStore = CustomMascotStore(root)
        val libraryStore = CustomMascotStore(root)
        assertTrue(libraryStore.entries().isEmpty())

        assertIs<MascotInstallResult.Installed>(installer(installerStore).install(validManifest()))

        assertEquals("code_import", libraryStore.observeEntries().first().single().source)
    }

    private fun installer(store: CustomMascotStore) = MascotPackageInstaller(
        store,
        MascotAssetDownloader { BYTES },
        verifier(),
    )

    private fun verifier() = MascotAssetVerifier { 24 to 24 }

    private fun validManifest(): MascotImportManifest {
        val checksum = BYTES.sha256()
        fun asset(role: MascotPoseRole) = MascotImportAsset(
            poseId = role.name.lowercase(), role = role,
            assetUrl = "https://assets.example.invalid/${role.name.lowercase()}.png",
            sha256 = checksum, expectedBytes = BYTES.size.toLong(), mimeType = "image/png",
            width = 24, height = 24,
        )
        val poses = MascotPoseRole.entries.map(::asset)
        return MascotImportManifest(1, "bob", "v1", "Bob", MascotVisibility.PUBLIC, poses.first(), poses)
    }

    private fun ByteArray.sha256(): String = MessageDigest.getInstance("SHA-256").digest(this)
        .joinToString("") { "%02x".format(it) }

    private companion object { val BYTES = byteArrayOf(1, 2, 3, 4) }
}

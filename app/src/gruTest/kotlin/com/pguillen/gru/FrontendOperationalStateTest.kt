package com.pguillen.gru

import com.pguillen.gru.dictation.TranscriptionEngine
import com.pguillen.gru.local.WhisperModelError
import com.pguillen.gru.local.WhisperModelState
import java.io.File
import com.pguillen.gru.mascot.CustomMascotEntry
import com.pguillen.gru.mascot.MascotSource
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue
import kotlin.test.assertFalse

class FrontendOperationalStateTest {
    @Test fun `removing the active custom mascot requires built in fallback`() {
        val entry = CustomMascotEntry("package", "mascot", "preview", true, 0L, "Bob")
        assertEquals(true, isActiveCustomMascot(MascotSource.Custom("package", "mascot"), entry))
        assertEquals(false, isActiveCustomMascot(MascotSource.Custom("other", "mascot"), entry))
        val order = mutableListOf<String>()
        assertTrue(removeImportedMascotSafely(
            source = MascotSource.Custom("package", "mascot"),
            entry = entry,
            selectFallback = { order += "fallback" },
            remove = { order += "remove"; true },
        ))
        assertEquals(listOf("fallback", "remove"), order)
    }

    @Test fun `failed active mascot removal restores previous selection`() {
        val entry = CustomMascotEntry("package", "mascot", "preview", true, 0L, "Bob", source = "code_import")
        val order = mutableListOf<String>()
        assertFalse(removeImportedMascotSafely(
            source = MascotSource.Custom("package", "mascot"),
            entry = entry,
            selectFallback = { order += "fallback" },
            restoreSelection = { order += "restore" },
            remove = { order += "remove"; false },
        ))
        assertEquals(listOf("fallback", "remove", "restore"), order)
    }

    @Test fun `my mascots contains only code imports`() {
        val imported = CustomMascotEntry("imported", "one", "preview", true, 0L, "Bob", source = "code_import")
        val legacy = CustomMascotEntry("legacy", "two", "preview", true, 0L, "Old", source = "legacy_custom")
        assertEquals(listOf(imported), importedMascotEntries(listOf(legacy, imported)))
    }

    @Test fun `built in gallery exposes five real assets and reserves sixth for future`() {
        assertEquals(5, currentBuiltInMascotCount)
        assertEquals(6, PLANNED_BUILT_IN_MASCOT_COUNT)
    }
    @Test fun `permission roles distinguish attention error and success`() {
        assertEquals(PermissionVisualState.ATTENTION, permissionVisualState(granted = false))
        assertEquals(PermissionVisualState.ERROR, permissionVisualState(granted = false, failed = true))
        assertEquals(PermissionVisualState.SUCCESS, permissionVisualState(granted = true))
    }

    @Test fun `requested private without model is preparing not active`() {
        assertEquals(
            VoiceModeVisualState.PREPARING,
            voiceModeVisualState(
                TranscriptionEngine.PRIVATE_LOCAL,
                current = null,
                requested = TranscriptionEngine.PRIVATE_LOCAL,
                privateModelState = WhisperModelState.NotInstalled,
            ),
        )
    }

    @Test fun `private state uses success only when actually active`() {
        assertEquals(
            VoiceModeVisualState.ACTIVE,
            voiceModeVisualState(
                TranscriptionEngine.PRIVATE_LOCAL,
                current = TranscriptionEngine.PRIVATE_LOCAL,
                requested = null,
                privateModelState = WhisperModelState.Installed(File("model.bin"), 1L),
            ),
        )
    }

    @Test fun `private model failure is error`() {
        assertEquals(
            VoiceModeVisualState.ERROR,
            voiceModeVisualState(
                TranscriptionEngine.PRIVATE_LOCAL,
                current = null,
                requested = TranscriptionEngine.PRIVATE_LOCAL,
                privateModelState = WhisperModelState.Error(WhisperModelError.NETWORK),
            ),
        )
    }
}

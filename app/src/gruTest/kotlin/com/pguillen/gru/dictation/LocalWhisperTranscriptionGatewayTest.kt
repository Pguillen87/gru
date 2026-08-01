/*
 * Copyright (C) 2026 Gru Contributors
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 */

package com.pguillen.gru.dictation

import com.pguillen.gru.local.LocalWhisperTranscriber
import com.pguillen.gru.local.WhisperModelProvider
import java.io.File
import java.io.IOException
import kotlin.io.path.createTempFile
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlinx.coroutines.test.runTest

class LocalWhisperTranscriptionGatewayTest {
    private val audio = temporaryFile("audio")
    private val model = temporaryFile("model")

    @Test
    fun `fails locally when model is absent without invoking runtime`() = runTest {
        var runtimeCalled = false
        val gateway = LocalWhisperTranscriptionGateway(
            modelManager = WhisperModelProvider { null },
            runtime = LocalWhisperTranscriber { _, _ -> runtimeCalled = true; "unexpected" },
        )

        val error = assertFailsWith<GruTranscriptionException> { gateway.transcribe(audio) }

        assertEquals(GruDictationFailure.LOCAL_MODEL_MISSING, error.failure)
        assertEquals(false, runtimeCalled)
    }

    @Test
    fun `returns local transcript without another provider`() = runTest {
        val gateway = LocalWhisperTranscriptionGateway(
            modelManager = WhisperModelProvider { model },
            runtime = LocalWhisperTranscriber { selectedModel, selectedAudio ->
                assertEquals(model, selectedModel)
                assertEquals(audio, selectedAudio)
                "texto privado"
            },
        )

        assertEquals("texto privado", gateway.transcribe(audio))
    }

    @Test
    fun `maps local runtime failure`() = runTest {
        val gateway = LocalWhisperTranscriptionGateway(
            modelManager = WhisperModelProvider { model },
            runtime = LocalWhisperTranscriber { _, _ -> throw IOException("local failure") },
        )

        val error = assertFailsWith<GruTranscriptionException> { gateway.transcribe(audio) }
        assertEquals(GruDictationFailure.LOCAL_RUNTIME, error.failure)
    }

    private fun temporaryFile(content: String): File = createTempFile("gru-local", ".tmp").toFile().apply {
        writeText(content)
        deleteOnExit()
    }
}

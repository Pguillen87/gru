/*
 * Copyright (C) 2026 Gru Contributors
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 */

package dev.patrickgold.florisboard.gru.dictation

import java.io.File
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.advanceTimeBy
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertIs
import kotlin.test.assertTrue

@OptIn(ExperimentalCoroutinesApi::class)
class GruSessionCoordinatorTest {
    @Test
    fun `records transcribes inserts and returns to idle`() = runTest {
        val audio = temporaryAudio()
        val response = CompletableDeferred<String>()
        val capture = FakeCapture(GruRecording(audio, 1_000L, 2_000))
        var inserted = ""
        val coordinator = GruSessionCoordinator(
            scope = this,
            captureFactory = { capture },
            transcription = GruTranscriptionGateway { response.await() },
            textTarget = GruTextTarget { text -> inserted = text; true },
            nowMillis = { testScheduler.currentTime },
        )

        coordinator.startRecording()
        assertIs<GruDictationState.Recording>(coordinator.state.value)

        coordinator.stopAndTranscribe()
        runCurrent()
        assertIs<GruDictationState.Transcribing>(coordinator.state.value)

        response.complete("Texto ditado")
        runCurrent()
        assertEquals("Texto ditado", inserted)
        assertIs<GruDictationState.Success>(coordinator.state.value)

        advanceTimeBy(1_200L)
        runCurrent()
        assertIs<GruDictationState.Idle>(coordinator.state.value)
        assertFalse(audio.exists())
    }

    @Test
    fun `rejects silent recording without calling provider`() = runTest {
        val audio = temporaryAudio()
        var providerCalled = false
        val coordinator = GruSessionCoordinator(
            scope = this,
            captureFactory = { FakeCapture(GruRecording(audio, 1_000L, 10)) },
            transcription = GruTranscriptionGateway { providerCalled = true; "unexpected" },
            textTarget = GruTextTarget { true },
            nowMillis = { testScheduler.currentTime },
        )

        coordinator.startRecording()
        coordinator.stopAndTranscribe()
        runCurrent()

        assertEquals(GruDictationFailure.NO_SPEECH, assertIs<GruDictationState.Error>(coordinator.state.value).reason)
        assertFalse(providerCalled)
        assertFalse(audio.exists())
    }

    @Test
    fun `surfaces insertion refusal`() = runTest {
        val audio = temporaryAudio()
        val coordinator = GruSessionCoordinator(
            scope = this,
            captureFactory = { FakeCapture(GruRecording(audio, 800L, 1_500)) },
            transcription = GruTranscriptionGateway { "texto" },
            textTarget = GruTextTarget { false },
            nowMillis = { testScheduler.currentTime },
        )

        coordinator.startRecording()
        coordinator.stopAndTranscribe()
        runCurrent()

        assertEquals(
            GruDictationFailure.INSERTION_REJECTED,
            assertIs<GruDictationState.Error>(coordinator.state.value).reason,
        )
        assertFalse(audio.exists())
    }

    @Test
    fun `recording speech threshold requires duration level and audio data`() {
        val valid = temporaryAudio()
        assertTrue(GruRecording(valid, 350L, 120).hasSpeech)
        assertFalse(GruRecording(valid, 349L, 120).hasSpeech)
        assertFalse(GruRecording(valid, 350L, 119).hasSpeech)
        valid.delete()
    }

    private fun temporaryAudio(): File = kotlin.io.path.createTempFile("gru", ".wav").toFile().apply {
        writeBytes(ByteArray(128))
    }

    private class FakeCapture(private val recording: GruRecording) : GruAudioCapture {
        override fun start() = Unit
        override fun level(): Float = 0.5f
        override fun stop(): GruRecording = recording
        override fun cancel() = Unit
    }
}

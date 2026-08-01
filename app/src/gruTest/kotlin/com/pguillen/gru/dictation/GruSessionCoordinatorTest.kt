/*
 * Copyright (C) 2026 Gru Contributors
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 */

package com.pguillen.gru.dictation

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
            transcriptionFactory = GruTranscriptionGatewayFactory {
                GruTranscriptionGateway { response.await() }
            },
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
            transcriptionFactory = GruTranscriptionGatewayFactory {
                GruTranscriptionGateway { providerCalled = true; "unexpected" }
            },
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
            transcriptionFactory = GruTranscriptionGatewayFactory { GruTranscriptionGateway { "texto" } },
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
    fun `cancels active capture and returns to idle`() = runTest {
        val capture = FakeCapture(GruRecording(temporaryAudio(), 800L, 1_500))
        val coordinator = coordinator(capture = capture)

        coordinator.startRecording()
        coordinator.cancel()

        assertTrue(capture.canceled)
        assertIs<GruDictationState.Idle>(coordinator.state.value)
    }

    @Test
    fun `ignores repeated starts while a session is active`() = runTest {
        var capturesCreated = 0
        val capture = FakeCapture(GruRecording(temporaryAudio(), 800L, 1_500))
        val coordinator = GruSessionCoordinator(
            scope = this,
            captureFactory = { capturesCreated++; capture },
            transcriptionFactory = GruTranscriptionGatewayFactory { GruTranscriptionGateway { "texto" } },
            textTarget = GruTextTarget { true },
            nowMillis = { testScheduler.currentTime },
        )

        coordinator.startRecording()
        coordinator.startRecording()

        assertEquals(1, capturesCreated)
        assertIs<GruDictationState.Recording>(coordinator.state.value)
        coordinator.cancel()
    }

    @Test
    fun `preserves expected transcription failures`() = runTest {
        val failures = listOf(
            GruDictationFailure.EMPTY_RESPONSE,
            GruDictationFailure.NETWORK,
            GruDictationFailure.PROVIDER,
        )

        failures.forEach { failure ->
            val audio = temporaryAudio()
            val coordinator = coordinator(
                capture = FakeCapture(GruRecording(audio, 800L, 1_500)),
                transcription = GruTranscriptionGateway { throw GruTranscriptionException(failure) },
            )
            coordinator.startRecording()
            coordinator.stopAndTranscribe()
            runCurrent()

            assertEquals(failure, assertIs<GruDictationState.Error>(coordinator.state.value).reason)
            assertFalse(audio.exists())
        }
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

    private fun kotlinx.coroutines.test.TestScope.coordinator(
        capture: FakeCapture,
        transcription: GruTranscriptionGateway = GruTranscriptionGateway { "texto" },
    ) = GruSessionCoordinator(
        scope = this,
        captureFactory = { capture },
        transcriptionFactory = GruTranscriptionGatewayFactory { transcription },
        textTarget = GruTextTarget { true },
        nowMillis = { testScheduler.currentTime },
    )

    private class FakeCapture(private val recording: GruRecording) : GruAudioCapture {
        var canceled = false

        override fun start() = Unit
        override fun level(): Float = 0.5f
        override fun stop(): GruRecording = recording
        override fun cancel() {
            canceled = true
            recording.file.delete()
        }
    }
}

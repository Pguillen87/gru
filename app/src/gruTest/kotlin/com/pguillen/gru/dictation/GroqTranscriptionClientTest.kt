/*
 * Copyright (C) 2026 Gru Contributors
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 */

package com.pguillen.gru.dictation

import java.io.File
import kotlinx.coroutines.test.runTest
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertIs
import kotlin.test.assertTrue

class GroqTranscriptionClientTest {
    @Test
    fun `uploads wav to Groq compatible endpoint`() = runTest {
        val server = MockWebServer()
        server.enqueue(MockResponse().setBody("{\"text\":\" Texto ditado \"}"))
        server.start()
        try {
            val audio = File.createTempFile("gru-audio", ".wav").apply {
                writeBytes(byteArrayOf(1, 2, 3, 4))
                deleteOnExit()
            }
            val client = GroqTranscriptionClient(endpoint = server.url("audio/transcriptions").toString())

            assertEquals("Texto ditado", client.transcribe(audio, "secret", "whisper-test"))

            val request = server.takeRequest()
            assertEquals("Bearer secret", request.getHeader("Authorization"))
            assertTrue(request.body.readUtf8().contains("whisper-test"))
        } finally {
            server.shutdown()
        }
    }

    @Test
    fun `maps HTTP rejection to provider failure`() = runTest {
        val server = MockWebServer()
        server.enqueue(MockResponse().setResponseCode(401).setBody("{\"error\":\"invalid key\"}"))
        server.start()
        try {
            val audio = File.createTempFile("gru-audio", ".wav").apply { writeBytes(byteArrayOf(1)) }
            val client = GroqTranscriptionClient(endpoint = server.url("audio/transcriptions").toString())
            val settings = object : GruTranscriptionSettings {
                override val apiKey = "invalid"
                override val model = "whisper-test"
            }
            val error = runCatching {
                GroqTranscriptionGateway(settings, client).transcribe(audio)
            }.exceptionOrNull()

            assertIs<GruTranscriptionException>(error)
            assertEquals(GruDictationFailure.PROVIDER, error.failure)
        } finally {
            server.shutdown()
        }
    }
}

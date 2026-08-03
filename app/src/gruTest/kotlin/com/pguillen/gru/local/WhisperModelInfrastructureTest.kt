/*
 * Copyright (C) 2026 Gru Contributors
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 */

package com.pguillen.gru.local

import java.io.File
import java.security.MessageDigest
import kotlinx.coroutines.test.runTest
import okhttp3.OkHttpClient
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertNull
import kotlin.test.assertTrue

class WhisperModelInfrastructureTest {
    @Test
    fun `pins the production Base Q5_1 model`() {
        val model = GruWhisperModel.BASE_Q5_1

        assertEquals("ggml-base-q5_1.bin", model.fileName)
        assertEquals(59_707_625L, model.expectedBytes)
        assertEquals("422f1ae452ade6f30a004d7e5c6a43195e4433bc370bf23fac9cc591f01a8898", model.sha256)
        assertTrue(model.downloadUrl.contains(model.version.substringAfter('@')))
    }

    @Test
    fun `accepts only expected model size and checksum`() {
        val bytes = "private whisper model".encodeToByteArray()
        val file = temporaryFile(bytes)
        val spec = specFor(file, bytes)
        val verifier = WhisperModelVerifier()

        assertNull(verifier.validate(file, spec))
        file.appendBytes(byteArrayOf(0))
        assertEquals(WhisperModelError.INVALID_SIZE, verifier.validate(file, spec))
    }

    @Test
    fun `rejects same-size model with invalid checksum`() {
        val expected = "expected".encodeToByteArray()
        val file = temporaryFile("modified".encodeToByteArray())

        assertEquals(
            WhisperModelError.INVALID_CHECKSUM,
            WhisperModelVerifier().validate(file, specFor(file, expected)),
        )
    }

    @Test
    fun `downloads model and reports final progress`() = runTest {
        val bytes = ByteArray(4_096) { (it % 251).toByte() }
        val server = MockWebServer().apply {
            enqueue(MockResponse().setBody(okio.Buffer().write(bytes)))
            start()
        }
        try {
            val target = temporaryFile(byteArrayOf()).apply { delete() }
            var progress = 0L
            WhisperModelDownloader(OkHttpClient()).download(
                specFor(target, bytes, server.url("model.bin").toString()),
                target,
            ) { progress = it }

            assertContentEquals(bytes, target.readBytes())
            assertEquals(bytes.size.toLong(), progress)
        } finally {
            server.shutdown()
        }
    }

    @Test
    fun `resumes managed partial download with range request`() = runTest {
        val full = "0123456789".encodeToByteArray()
        val target = temporaryFile(full.copyOfRange(0, 4))
        val server = MockWebServer().apply {
            enqueue(MockResponse().setResponseCode(206).setBody(okio.Buffer().write(full.copyOfRange(4, full.size))))
            start()
        }
        try {
            WhisperModelDownloader(OkHttpClient()).download(
                specFor(target, full, server.url("model.bin").toString()),
                target,
            ) { }

            assertEquals("bytes=4-", server.takeRequest().getHeader("Range"))
            assertContentEquals(full, target.readBytes())
        } finally {
            server.shutdown()
        }
    }

    private fun specFor(file: File, expected: ByteArray, url: String = "https://example.invalid/model") =
        WhisperModelSpec(
            id = "test",
            version = "test-revision",
            fileName = file.name,
            downloadUrl = url,
            expectedBytes = expected.size.toLong(),
            sha256 = sha256(expected),
        )

    private fun temporaryFile(bytes: ByteArray): File =
        kotlin.io.path.createTempFile("gru-model", ".bin").toFile().apply {
            writeBytes(bytes)
            deleteOnExit()
        }

    private fun sha256(bytes: ByteArray): String = MessageDigest.getInstance("SHA-256")
        .digest(bytes)
        .joinToString("") { "%02x".format(it) }
}

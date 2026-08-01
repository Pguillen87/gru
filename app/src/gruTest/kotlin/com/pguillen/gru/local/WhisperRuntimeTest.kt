/*
 * Copyright (C) 2026 Gru Contributors
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 */

package com.pguillen.gru.local

import java.io.ByteArrayOutputStream
import java.io.DataOutputStream
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import kotlin.io.path.createTempFile
import kotlin.test.Test
import kotlin.test.assertTrue
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.yield

class WhisperRuntimeTest {
    @Test
    fun `cancelling coroutine aborts native inference and releases model`() = runBlocking {
        val native = BlockingWhisperNative()
        val runtime = WhisperRuntime(native)
        val job = launch { runtime.transcribe(temporaryFile("model"), wavFile()) }
        yield()
        assertTrue(native.started.await(2, TimeUnit.SECONDS))

        job.cancelAndJoin()
        runtime.release()

        assertTrue(native.cancelled)
        assertTrue(native.destroyed)
    }

    private class BlockingWhisperNative : WhisperNative {
        val started = CountDownLatch(1)
        @Volatile var cancelled = false
        @Volatile var destroyed = false

        override fun create(modelPath: String): Long = 7L

        override fun transcribe(handle: Long, samples: FloatArray, language: String, threadCount: Int): String {
            started.countDown()
            while (!cancelled) Thread.sleep(5)
            error("cancelled")
        }

        override fun cancel(handle: Long) {
            cancelled = true
        }

        override fun destroy(handle: Long) {
            destroyed = true
        }
    }

    private fun wavFile(): File {
        val pcm = ByteBuffer.allocate(320).order(ByteOrder.LITTLE_ENDIAN)
            .apply { repeat(160) { putShort(1.toShort()) } }
            .array()
        val body = ByteArrayOutputStream().also { bytes ->
            DataOutputStream(bytes).use { output ->
                output.writeBytes("WAVEfmt ")
                output.writeInt(Integer.reverseBytes(16))
                output.writeShort(java.lang.Short.reverseBytes(1).toInt())
                output.writeShort(java.lang.Short.reverseBytes(1).toInt())
                output.writeInt(Integer.reverseBytes(16_000))
                output.writeInt(Integer.reverseBytes(32_000))
                output.writeShort(java.lang.Short.reverseBytes(2).toInt())
                output.writeShort(java.lang.Short.reverseBytes(16).toInt())
                output.writeBytes("data")
                output.writeInt(Integer.reverseBytes(pcm.size))
                output.write(pcm)
            }
        }.toByteArray()
        return createTempFile("gru-runtime", ".wav").toFile().apply {
            DataOutputStream(outputStream()).use { output ->
                output.writeBytes("RIFF")
                output.writeInt(Integer.reverseBytes(body.size))
                output.write(body)
            }
            deleteOnExit()
        }
    }

    private fun temporaryFile(content: String): File = createTempFile("gru-runtime", ".bin").toFile().apply {
        writeText(content)
        deleteOnExit()
    }
}

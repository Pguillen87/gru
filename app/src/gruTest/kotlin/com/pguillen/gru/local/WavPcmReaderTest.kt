/*
 * Copyright (C) 2026 Gru Contributors
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 */

package com.pguillen.gru.local

import java.io.ByteArrayOutputStream
import java.io.DataOutputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder
import kotlin.io.path.createTempFile
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertFailsWith

class WavPcmReaderTest {
    @Test
    fun `reads mono 16 kHz PCM16 samples with extra chunks`() {
        val file = createTempFile("gru-audio", ".wav").toFile().apply {
            writeBytes(wav(sampleRate = 16_000, samples = shortArrayOf(0, Short.MAX_VALUE, Short.MIN_VALUE)))
            deleteOnExit()
        }

        assertContentEquals(floatArrayOf(0f, Short.MAX_VALUE / 32768f, -1f), WavPcmReader().read(file))
    }

    @Test
    fun `rejects unsupported sample rate`() {
        val file = createTempFile("gru-audio", ".wav").toFile().apply {
            writeBytes(wav(sampleRate = 44_100, samples = shortArrayOf(1)))
            deleteOnExit()
        }

        assertFailsWith<IllegalArgumentException> { WavPcmReader().read(file) }
    }

    private fun wav(sampleRate: Int, samples: ShortArray): ByteArray {
        val pcm = ByteBuffer.allocate(samples.size * 2).order(ByteOrder.LITTLE_ENDIAN)
            .apply { samples.forEach(::putShort) }
            .array()
        val body = ByteArrayOutputStream().also { bytes ->
            DataOutputStream(bytes).use { output ->
                output.writeBytes("WAVE")
                output.writeBytes("JUNK")
                output.writeInt(Integer.reverseBytes(2))
                output.write(byteArrayOf(1, 2))
                output.writeBytes("fmt ")
                output.writeInt(Integer.reverseBytes(16))
                output.writeShort(java.lang.Short.reverseBytes(1).toInt())
                output.writeShort(java.lang.Short.reverseBytes(1).toInt())
                output.writeInt(Integer.reverseBytes(sampleRate))
                output.writeInt(Integer.reverseBytes(sampleRate * 2))
                output.writeShort(java.lang.Short.reverseBytes(2).toInt())
                output.writeShort(java.lang.Short.reverseBytes(16).toInt())
                output.writeBytes("data")
                output.writeInt(Integer.reverseBytes(pcm.size))
                output.write(pcm)
            }
        }.toByteArray()
        return ByteArrayOutputStream().also { bytes ->
            DataOutputStream(bytes).use { output ->
                output.writeBytes("RIFF")
                output.writeInt(Integer.reverseBytes(body.size))
                output.write(body)
            }
        }.toByteArray()
    }
}

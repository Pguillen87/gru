/*
 * Copyright (C) 2026 Gru Contributors
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 */

package com.pguillen.gru.local

import java.io.EOFException
import java.io.File
import java.io.RandomAccessFile
import java.nio.ByteBuffer
import java.nio.ByteOrder

internal class WavPcmReader {
    fun read(file: File): FloatArray = RandomAccessFile(file, "r").use { input ->
        require(input.readAscii(4) == "RIFF" && input.skipBytes(4) == 4 && input.readAscii(4) == "WAVE") {
            "Invalid WAV header"
        }
        var format: WavFormat? = null
        var samples: FloatArray? = null
        while (input.filePointer + CHUNK_HEADER_BYTES <= input.length()) {
            val id = input.readAscii(4)
            val size = input.readUInt32LittleEndian()
            require(size <= Int.MAX_VALUE) { "WAV chunk is too large" }
            when (id) {
                "fmt " -> format = input.readFormat(size.toInt())
                "data" -> samples = input.readSamples(size.toInt(), requireNotNull(format) { "Missing WAV format" })
                else -> input.seek(input.filePointer + size)
            }
            if (size % 2L != 0L && input.filePointer < input.length()) input.skipBytes(1)
            if (samples != null) break
        }
        requireNotNull(samples) { "Missing WAV audio data" }
    }

    private fun RandomAccessFile.readFormat(size: Int): WavFormat {
        require(size >= PCM_FORMAT_BYTES) { "Invalid WAV format" }
        val bytes = ByteArray(size)
        readFully(bytes)
        val buffer = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN)
        val encoding = buffer.short.toInt() and 0xffff
        val channels = buffer.short.toInt() and 0xffff
        val sampleRate = buffer.int
        buffer.position(buffer.position() + 6)
        val bitsPerSample = buffer.short.toInt() and 0xffff
        require(encoding == PCM_ENCODING && channels == 1 && sampleRate == SAMPLE_RATE && bitsPerSample == 16) {
            "Whisper requires mono 16 kHz PCM16 WAV"
        }
        return WavFormat(bitsPerSample)
    }

    private fun RandomAccessFile.readSamples(size: Int, format: WavFormat): FloatArray {
        val bytesPerSample = format.bitsPerSample / 8
        require(size % bytesPerSample == 0) { "Invalid WAV data length" }
        val bytes = ByteArray(size)
        readFully(bytes)
        val buffer = ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN)
        return FloatArray(size / bytesPerSample) { buffer.short / 32768f }
    }

    private fun RandomAccessFile.readAscii(length: Int): String {
        val bytes = ByteArray(length)
        if (read(bytes) != length) throw EOFException()
        return bytes.toString(Charsets.US_ASCII)
    }

    private fun RandomAccessFile.readUInt32LittleEndian(): Long {
        val bytes = ByteArray(4)
        readFully(bytes)
        return ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN).int.toLong() and 0xffffffffL
    }

    private data class WavFormat(val bitsPerSample: Int)

    private companion object {
        const val CHUNK_HEADER_BYTES = 8L
        const val PCM_FORMAT_BYTES = 16
        const val PCM_ENCODING = 1
        const val SAMPLE_RATE = 16_000
    }
}

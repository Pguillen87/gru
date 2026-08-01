/*
 * Copyright (C) 2026 Gru Contributors
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 */

package com.pguillen.gru.local

import java.io.File
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicLong
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException
import kotlinx.coroutines.suspendCancellableCoroutine

internal fun interface LocalWhisperTranscriber {
    suspend fun transcribe(model: File, audio: File): String
}

internal class WhisperRuntime(
    private val native: WhisperNative = JniWhisperNative,
    private val wavReader: WavPcmReader = WavPcmReader(),
) : LocalWhisperTranscriber {
    private val executor = Executors.newSingleThreadExecutor { task ->
        Thread(task, "gru-whisper").apply { priority = Thread.NORM_PRIORITY - 1 }
    }
    private val activeHandle = AtomicLong(NO_HANDLE)
    private var loadedPath: String? = null
    private var handle: Long = NO_HANDLE

    override suspend fun transcribe(model: File, audio: File): String = suspendCancellableCoroutine { continuation ->
        continuation.invokeOnCancellation {
            activeHandle.get().takeIf { it != NO_HANDLE }?.let(native::cancel)
        }
        executor.execute {
            try {
                val currentHandle = load(model)
                activeHandle.set(currentHandle)
                val samples = wavReader.read(audio)
                val result = native.transcribe(currentHandle, samples, LANGUAGE_PORTUGUESE, threadCount())
                if (continuation.isActive) continuation.resume(result.trim())
            } catch (error: Throwable) {
                if (continuation.isActive) continuation.resumeWithException(error)
            } finally {
                activeHandle.set(NO_HANDLE)
            }
        }
    }

    fun release() {
        activeHandle.get().takeIf { it != NO_HANDLE }?.let(native::cancel)
        executor.execute {
            if (handle != NO_HANDLE) native.destroy(handle)
            handle = NO_HANDLE
            loadedPath = null
        }
    }

    private fun load(model: File): Long {
        if (handle != NO_HANDLE && loadedPath == model.absolutePath) return handle
        if (handle != NO_HANDLE) native.destroy(handle)
        handle = native.create(model.absolutePath)
        check(handle != NO_HANDLE) { "Whisper returned an invalid model handle" }
        loadedPath = model.absolutePath
        return handle
    }

    private fun threadCount(): Int = Runtime.getRuntime().availableProcessors().coerceIn(1, MAX_THREADS)

    private companion object {
        const val NO_HANDLE = 0L
        const val MAX_THREADS = 4
        const val LANGUAGE_PORTUGUESE = "pt"
    }
}

internal interface WhisperNative {
    fun create(modelPath: String): Long
    fun transcribe(handle: Long, samples: FloatArray, language: String, threadCount: Int): String
    fun cancel(handle: Long)
    fun destroy(handle: Long)
}

private object JniWhisperNative : WhisperNative {
    override fun create(modelPath: String): Long = WhisperNativeBridge.create(modelPath)
    override fun transcribe(handle: Long, samples: FloatArray, language: String, threadCount: Int): String =
        WhisperNativeBridge.transcribe(handle, samples, language, threadCount)
    override fun cancel(handle: Long) = WhisperNativeBridge.cancel(handle)
    override fun destroy(handle: Long) = WhisperNativeBridge.destroy(handle)
}

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
import com.pguillen.gru.dictation.GruDiagnostics
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException
import kotlinx.coroutines.suspendCancellableCoroutine

internal fun interface LocalWhisperTranscriber {
    suspend fun transcribe(model: File, audio: File): String
}

internal data class WhisperRuntimeMetrics(
    val modelLoadMillis: Long,
    val inferenceMillis: Long,
    val audioDurationMillis: Long,
) {
    val realTimeFactor: Double
        get() = inferenceMillis.toDouble() / audioDurationMillis.coerceAtLeast(1L)
}

internal class WhisperRuntime(
    private val native: WhisperNative = JniWhisperNative,
    private val wavReader: WavPcmReader = WavPcmReader(),
    private val nativeBackendDirectory: String? = null,
    private val inferenceThreads: Int = DEFAULT_THREAD_COUNT,
) : LocalWhisperTranscriber {
    private val executor = Executors.newSingleThreadExecutor { task ->
        Thread(task, "gru-whisper").apply { priority = Thread.NORM_PRIORITY }
    }
    private val activeHandle = AtomicLong(NO_HANDLE)
    private var loadedPath: String? = null
    private var handle: Long = NO_HANDLE
    @Volatile var lastMetrics: WhisperRuntimeMetrics? = null
        private set

    override suspend fun transcribe(model: File, audio: File): String = suspendCancellableCoroutine { continuation ->
        continuation.invokeOnCancellation {
            activeHandle.get().takeIf { it != NO_HANDLE }?.let(native::cancel)
        }
        executor.execute {
            try {
                val loadStarted = System.nanoTime()
                val alreadyLoaded = handle != NO_HANDLE && loadedPath == model.absolutePath
                val currentHandle = load(model)
                val loadMillis = if (alreadyLoaded) 0L else elapsedMillis(loadStarted)
                activeHandle.set(currentHandle)
                val samples = wavReader.read(audio)
                val inferenceStarted = System.nanoTime()
                val result = native.transcribe(currentHandle, samples, LANGUAGE_PORTUGUESE, threadCount())
                lastMetrics = WhisperRuntimeMetrics(
                    modelLoadMillis = loadMillis,
                    inferenceMillis = elapsedMillis(inferenceStarted),
                    audioDurationMillis = samples.size * 1_000L / SAMPLE_RATE,
                )
                GruDiagnostics.info(
                    "Local transcription completed loadMs=$loadMillis " +
                        "inferenceMs=${lastMetrics?.inferenceMillis} " +
                        "audioMs=${lastMetrics?.audioDurationMillis} threads=${threadCount()}",
                )
                if (continuation.isActive) continuation.resume(result.trim())
            } catch (error: Throwable) {
                if (continuation.isActive) continuation.resumeWithException(error)
            } finally {
                activeHandle.set(NO_HANDLE)
            }
        }
    }

    suspend fun release() = suspendCancellableCoroutine { continuation ->
        activeHandle.get().takeIf { it != NO_HANDLE }?.let(native::cancel)
        executor.execute {
            try {
                if (handle != NO_HANDLE) native.destroy(handle)
                handle = NO_HANDLE
                loadedPath = null
                if (continuation.isActive) continuation.resume(Unit)
            } catch (error: Throwable) {
                if (continuation.isActive) continuation.resumeWithException(error)
            }
        }
    }

    private fun load(model: File): Long {
        if (handle != NO_HANDLE && loadedPath == model.absolutePath) return handle
        if (handle != NO_HANDLE) native.destroy(handle)
        handle = native.create(model.absolutePath, nativeBackendDirectory)
        check(handle != NO_HANDLE) { "Whisper returned an invalid model handle" }
        loadedPath = model.absolutePath
        return handle
    }

    private fun threadCount(): Int = inferenceThreads.coerceIn(
        1,
        Runtime.getRuntime().availableProcessors().coerceAtLeast(1),
    )

    private fun elapsedMillis(startedNanos: Long): Long = (System.nanoTime() - startedNanos) / 1_000_000L

    private companion object {
        const val NO_HANDLE = 0L
        const val DEFAULT_THREAD_COUNT = 4
        const val LANGUAGE_PORTUGUESE = "pt"
        const val SAMPLE_RATE = 16_000
    }
}

internal interface WhisperNative {
    fun create(modelPath: String, backendDirectory: String?): Long
    fun transcribe(handle: Long, samples: FloatArray, language: String, threadCount: Int): String
    fun cancel(handle: Long)
    fun destroy(handle: Long)
}

private object JniWhisperNative : WhisperNative {
    override fun create(modelPath: String, backendDirectory: String?): Long =
        WhisperNativeBridge.create(modelPath, backendDirectory)
    override fun transcribe(handle: Long, samples: FloatArray, language: String, threadCount: Int): String =
        WhisperNativeBridge.transcribe(handle, samples, language, threadCount)
    override fun cancel(handle: Long) = WhisperNativeBridge.cancel(handle)
    override fun destroy(handle: Long) = WhisperNativeBridge.destroy(handle)
}

/*
 * Copyright (C) 2026 Gru Contributors
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 */

package com.pguillen.gru

import android.os.Debug
import android.util.Log
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.pguillen.gru.local.WhisperRuntime
import java.io.File
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class WhisperBenchmarkInstrumentedTest {
    @Test
    fun benchmarkInstalledModelWithPreparedAudio() = runBlocking {
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val context = instrumentation.targetContext
        val modelName = InstrumentationRegistry.getArguments().getString(ARG_MODEL_NAME)
            ?.takeIf { it.matches(SAFE_FILE_NAME) }
            ?: DEFAULT_MODEL_NAME
        val threadCount = InstrumentationRegistry.getArguments().getString(ARG_THREAD_COUNT)
            ?.toIntOrNull()
            ?.coerceIn(MIN_THREADS, MAX_THREADS)
            ?: DEFAULT_THREAD_COUNT
        val audio = File(context.filesDir, BENCHMARK_AUDIO)
        val preparedModel = File(context.filesDir, "$BENCHMARK_MODEL_DIR/$modelName")
        assumeTrue("Push the requested model before benchmarking", preparedModel.exists())
        assumeTrue("Push a 16 kHz mono PCM16 WAV to app files before benchmarking", audio.exists())

        val pssBefore = Debug.getPss()
        val runtime = WhisperRuntime(
            nativeBackendDirectory = context.applicationInfo.nativeLibraryDir,
            inferenceThreads = threadCount,
        )
        try {
            val coldTranscript = withTimeout(BENCHMARK_TIMEOUT_MILLIS) {
                runtime.transcribe(preparedModel, audio)
            }
            val cold = requireNotNull(runtime.lastMetrics)
            val pssLoaded = Debug.getPss()
            val loadedBackend = File("/proc/self/maps").useLines { lines ->
                lines.firstOrNull { "libggml-cpu-" in it }
                    ?.substringAfterLast('/')
                    ?.substringBefore(' ')
                    ?: "static"
            }

            assertTrue(coldTranscript.isNotBlank())
            Log.i(
                TAG,
                "model=$modelName threads=$threadCount loadMs=${cold.modelLoadMillis} inferenceMs=${cold.inferenceMillis} " +
                    "audioMs=${cold.audioDurationMillis} rtf=${"%.3f".format(cold.realTimeFactor)} " +
                    "pssBeforeKb=$pssBefore pssLoadedKb=$pssLoaded backend=$loadedBackend " +
                    "transcript=${coldTranscript.replace('\n', ' ')}",
            )
        } finally {
            runtime.release()
        }
        Unit
    }

    private companion object {
        const val TAG = "GruWhisperBenchmark"
        const val BENCHMARK_AUDIO = "benchmark-pt.wav"
        const val BENCHMARK_MODEL_DIR = "benchmark-models"
        const val ARG_MODEL_NAME = "modelName"
        const val ARG_THREAD_COUNT = "threadCount"
        const val DEFAULT_MODEL_NAME = "ggml-small-q5_1.bin"
        const val DEFAULT_THREAD_COUNT = 4
        const val MIN_THREADS = 1
        const val MAX_THREADS = 8
        const val BENCHMARK_TIMEOUT_MILLIS = 600_000L
        val SAFE_FILE_NAME = Regex("[A-Za-z0-9._-]+")
    }
}

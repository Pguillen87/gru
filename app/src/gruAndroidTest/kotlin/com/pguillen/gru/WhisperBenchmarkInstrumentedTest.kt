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
import com.pguillen.gru.local.WhisperModelManager
import com.pguillen.gru.local.WhisperModelState
import com.pguillen.gru.local.WhisperRuntime
import java.io.File
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.flow.filterIsInstance
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.withTimeout
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class WhisperBenchmarkInstrumentedTest {
    @Test
    fun benchmarkInstalledModelWithPreparedAudio() = runBlocking {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val audio = File(context.filesDir, BENCHMARK_AUDIO)
        val installed = withTimeout(120_000L) {
            WhisperModelManager.get(context).state.filterIsInstance<WhisperModelState.Installed>().first()
        }
        val model = installed.file
        assumeTrue("Push a 16 kHz mono PCM16 WAV to app files before benchmarking", audio.exists())

        val pssBefore = Debug.getPss()
        val runtime = WhisperRuntime()
        try {
            val coldTranscript = runtime.transcribe(model, audio)
            val cold = requireNotNull(runtime.lastMetrics)
            val pssLoaded = Debug.getPss()
            val warmTranscript = runtime.transcribe(model, audio)
            val warm = requireNotNull(runtime.lastMetrics)
            val pssWarm = Debug.getPss()

            assertTrue(coldTranscript.isNotBlank())
            assertTrue(warmTranscript.isNotBlank())
            Log.i(
                TAG,
                "loadMs=${cold.modelLoadMillis} coldInferenceMs=${cold.inferenceMillis} " +
                    "warmInferenceMs=${warm.inferenceMillis} audioMs=${warm.audioDurationMillis} " +
                    "warmRtf=${"%.3f".format(warm.realTimeFactor)} " +
                    "pssBeforeKb=$pssBefore pssLoadedKb=$pssLoaded pssWarmKb=$pssWarm",
            )
        } finally {
            runtime.release()
            audio.delete()
        }
        Unit
    }

    private companion object {
        const val TAG = "GruWhisperBenchmark"
        const val BENCHMARK_AUDIO = "benchmark-pt.wav"
    }
}

/*
 * Copyright (C) 2026 Gru Contributors
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 */

package dev.patrickgold.florisboard.gru.dictation

import android.content.Context
import dev.patrickgold.florisboard.dictate.audio.RecordingController
import java.io.File

interface GruAudioCapture {
    fun start()
    fun level(): Float
    fun stop(): GruRecording?
    fun cancel()
}

data class GruRecording(
    val file: File,
    val durationMillis: Long,
    val peakAmplitude: Int,
) {
    val hasSpeech: Boolean
        get() = durationMillis >= MIN_DURATION_MILLIS &&
            peakAmplitude >= MIN_PEAK_AMPLITUDE &&
            file.length() > WAV_HEADER_BYTES

    private companion object {
        const val MIN_DURATION_MILLIS = 350L
        const val MIN_PEAK_AMPLITUDE = 120
        const val WAV_HEADER_BYTES = 44L
    }
}

class AndroidGruAudioCapture(
    context: Context,
    private val nowMillis: () -> Long = { android.os.SystemClock.elapsedRealtime() },
) : GruAudioCapture {
    private val recorder = RecordingController(context.applicationContext)
    private var startedAtMillis = 0L
    private var peakAmplitude = 0

    override fun start() {
        startedAtMillis = nowMillis()
        peakAmplitude = 0
        recorder.start()
    }

    override fun level(): Float {
        val amplitude = recorder.maxAmplitude()
        peakAmplitude = maxOf(peakAmplitude, amplitude)
        return (amplitude / Short.MAX_VALUE.toFloat()).coerceIn(0f, 1f)
    }

    override fun stop(): GruRecording? {
        val file = recorder.stop() ?: return null
        return GruRecording(
            file = file,
            durationMillis = (nowMillis() - startedAtMillis).coerceAtLeast(0L),
            peakAmplitude = peakAmplitude,
        )
    }

    override fun cancel() = recorder.cancel()
}

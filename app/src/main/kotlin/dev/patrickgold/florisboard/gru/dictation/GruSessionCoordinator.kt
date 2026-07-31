/*
 * Copyright (C) 2026 Gru Contributors
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 */

package dev.patrickgold.florisboard.gru.dictation

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import androidx.core.content.ContextCompat
import dev.patrickgold.florisboard.dictate.overlay.DictateAccessibilityService
import java.io.File
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

fun interface GruTextTarget {
    fun insert(text: String): Boolean
}

class GruSessionCoordinator(
    private val scope: CoroutineScope,
    private val captureFactory: () -> GruAudioCapture,
    private val transcription: GruTranscriptionGateway,
    private val textTarget: GruTextTarget,
    private val nowMillis: () -> Long,
) {
    private val mutableState = MutableStateFlow<GruDictationState>(GruDictationState.Idle)
    val state: StateFlow<GruDictationState> = mutableState.asStateFlow()

    private var capture: GruAudioCapture? = null
    private var levelJob: Job? = null
    private var transcriptionJob: Job? = null

    fun startRecording() {
        if (mutableState.value !is GruDictationState.Idle &&
            mutableState.value !is GruDictationState.Error &&
            mutableState.value !is GruDictationState.Success
        ) return
        val nextCapture = captureFactory()
        try {
            nextCapture.start()
        } catch (_: SecurityException) {
            mutableState.value = GruDictationState.Error(GruDictationFailure.MICROPHONE_PERMISSION)
            return
        } catch (_: Throwable) {
            mutableState.value = GruDictationState.Error(GruDictationFailure.MICROPHONE_UNAVAILABLE)
            return
        }
        capture = nextCapture
        val startedAt = nowMillis()
        mutableState.value = GruDictationState.Recording(startedAtMillis = startedAt)
        levelJob = scope.launch {
            while (true) {
                val level = nextCapture.level()
                mutableState.value = GruDictationState.Recording(
                    startedAtMillis = startedAt,
                    elapsedMillis = (nowMillis() - startedAt).coerceAtLeast(0L),
                    audioLevel = level,
                )
                delay(LEVEL_INTERVAL_MILLIS)
            }
        }
    }

    fun stopAndTranscribe() {
        if (mutableState.value !is GruDictationState.Recording) return
        transcriptionJob = scope.launch {
            levelJob?.cancelAndJoin()
            levelJob = null
            val recording = capture?.stop()
            capture = null
            if (recording == null || !recording.hasSpeech) {
                recording?.file?.delete()
                mutableState.value = GruDictationState.Error(GruDictationFailure.NO_SPEECH)
                return@launch
            }
            transcribeAndInsert(recording.file)
        }
    }

    fun cancel() {
        levelJob?.cancel()
        levelJob = null
        transcriptionJob?.cancel()
        transcriptionJob = null
        capture?.cancel()
        capture = null
        mutableState.value = GruDictationState.Idle
    }

    fun fail(reason: GruDictationFailure) {
        cancel()
        mutableState.value = GruDictationState.Error(reason)
    }

    private suspend fun transcribeAndInsert(audioFile: File) {
        mutableState.value = GruDictationState.Transcribing
        try {
            val text = transcription.transcribe(audioFile)
            if (!textTarget.insert(text)) {
                mutableState.value = GruDictationState.Error(GruDictationFailure.INSERTION_REJECTED)
                return
            }
            mutableState.value = GruDictationState.Success
            delay(SUCCESS_HOLD_MILLIS)
            mutableState.value = GruDictationState.Idle
        } catch (error: GruTranscriptionException) {
            mutableState.value = GruDictationState.Error(error.failure)
        } catch (_: Throwable) {
            mutableState.value = GruDictationState.Error(GruDictationFailure.UNKNOWN)
        } finally {
            audioFile.delete()
        }
    }

    private companion object {
        const val LEVEL_INTERVAL_MILLIS = 50L
        const val SUCCESS_HOLD_MILLIS = 1_200L
    }
}

object GruDictation {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
    private lateinit var coordinator: GruSessionCoordinator

    fun state(context: Context): StateFlow<GruDictationState> = instance(context).state

    fun onPetTapped(context: Context) {
        when (instance(context).state.value) {
            is GruDictationState.Recording -> instance().stopAndTranscribe()
            is GruDictationState.Transcribing -> Unit
            else -> {
                if (ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) !=
                    PackageManager.PERMISSION_GRANTED
                ) {
                    instance().fail(GruDictationFailure.MICROPHONE_PERMISSION)
                    return
                }
                instance().startRecording()
            }
        }
    }

    fun cancel() = instance().cancel()

    private fun instance(context: Context? = null): GruSessionCoordinator {
        if (!::coordinator.isInitialized) {
            val appContext = requireNotNull(context).applicationContext
            coordinator = GruSessionCoordinator(
                scope = scope,
                captureFactory = { AndroidGruAudioCapture(appContext) },
                transcription = GroqTranscriptionGateway(StoredGroqSettings(appContext)),
                textTarget = GruTextTarget(DictateAccessibilityService::injectText),
                nowMillis = android.os.SystemClock::elapsedRealtime,
            )
        }
        return coordinator
    }
}

/*
 * Copyright (C) 2026 Gru Contributors
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 */

package com.pguillen.gru.dictation

import com.pguillen.gru.local.LocalWhisperTranscriber
import com.pguillen.gru.local.WhisperModelProvider
import java.io.File
import kotlinx.coroutines.CancellationException

internal class LocalWhisperTranscriptionGateway(
    private val modelManager: WhisperModelProvider,
    private val runtime: LocalWhisperTranscriber,
) : GruTranscriptionGateway {
    override suspend fun transcribe(audioFile: File): String {
        val model = modelManager.installedModel()
            ?: throw GruTranscriptionException(GruDictationFailure.LOCAL_MODEL_MISSING)
        return try {
            runtime.transcribe(model, audioFile).ifBlank {
                throw GruTranscriptionException(GruDictationFailure.EMPTY_RESPONSE)
            }
        } catch (error: CancellationException) {
            throw error
        } catch (error: GruTranscriptionException) {
            throw error
        } catch (error: Throwable) {
            throw GruTranscriptionException(GruDictationFailure.LOCAL_RUNTIME, error)
        }
    }
}

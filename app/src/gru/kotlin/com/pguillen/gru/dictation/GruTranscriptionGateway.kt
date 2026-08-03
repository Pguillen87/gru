/*
 * Copyright (C) 2026 Gru Contributors
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 */

package com.pguillen.gru.dictation

import com.pguillen.gru.GruPreferences
import android.content.Context
import java.io.File
import java.io.IOException

fun interface GruTranscriptionGateway {
    suspend fun transcribe(audioFile: File): String
}

interface GruTranscriptionSettings {
    val apiKey: String
    val model: String
}

class StoredGroqSettings(context: Context) : GruTranscriptionSettings {
    private val prefs = GruPreferences.get(context)

    override val apiKey: String
        get() = prefs.groqApiKey

    override val model: String
        get() = prefs.groqModel
}

internal class GroqTranscriptionGateway(
    private val settings: GruTranscriptionSettings,
    private val client: GroqTranscriptionClient = GroqTranscriptionClient(),
) : GruTranscriptionGateway {
    override suspend fun transcribe(audioFile: File): String {
        val key = settings.apiKey.trim()
        if (key.isEmpty()) throw GruTranscriptionException(GruDictationFailure.MISSING_API_KEY)
        val startedAt = GruDiagnostics.nowMillis()
        return try {
            client.transcribe(audioFile, key, settings.model).ifEmpty {
                throw GruTranscriptionException(GruDictationFailure.EMPTY_RESPONSE)
            }.also {
                GruDiagnostics.info(
                    "Online transcription completed durationMs=${GruDiagnostics.nowMillis() - startedAt} " +
                        "audioBytes=${audioFile.length()}",
                )
            }
        } catch (error: GruTranscriptionException) {
            throw error
        } catch (error: GroqProviderException) {
            throw GruTranscriptionException(GruDictationFailure.PROVIDER, error)
        } catch (error: IOException) {
            throw GruTranscriptionException(GruDictationFailure.NETWORK, error)
        } catch (error: Throwable) {
            throw GruTranscriptionException(GruDictationFailure.PROVIDER, error)
        }
    }

}

class GruTranscriptionException(
    val failure: GruDictationFailure,
    cause: Throwable? = null,
) : Exception(cause)

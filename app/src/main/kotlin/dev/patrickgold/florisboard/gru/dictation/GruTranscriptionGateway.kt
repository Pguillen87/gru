/*
 * Copyright (C) 2026 Gru Contributors
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 */

package dev.patrickgold.florisboard.gru.dictation

import dev.patrickgold.florisboard.dictate.provider.OpenAiCompatibleClient
import dev.patrickgold.florisboard.dictate.provider.ProviderConfig
import dev.patrickgold.florisboard.dictate.provider.TranscriptionRequest
import dev.patrickgold.florisboard.gru.GruPreferences
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

class GroqTranscriptionGateway(
    private val settings: GruTranscriptionSettings,
) : GruTranscriptionGateway {
    override suspend fun transcribe(audioFile: File): String {
        val key = settings.apiKey.trim()
        if (key.isEmpty()) throw GruTranscriptionException(GruDictationFailure.MISSING_API_KEY)
        return try {
            OpenAiCompatibleClient(
                ProviderConfig(
                    baseUrl = GROQ_BASE_URL,
                    apiKey = key,
                ),
            ).transcribe(
                TranscriptionRequest(
                    audioFile = audioFile,
                    model = settings.model,
                ),
            ).text.trim().ifEmpty {
                throw GruTranscriptionException(GruDictationFailure.EMPTY_RESPONSE)
            }
        } catch (error: GruTranscriptionException) {
            throw error
        } catch (error: IOException) {
            throw GruTranscriptionException(GruDictationFailure.NETWORK, error)
        } catch (error: Throwable) {
            throw GruTranscriptionException(GruDictationFailure.PROVIDER, error)
        }
    }

    private companion object {
        const val GROQ_BASE_URL = "https://api.groq.com/openai/v1/"
    }
}

class GruTranscriptionException(
    val failure: GruDictationFailure,
    cause: Throwable? = null,
) : Exception(cause)

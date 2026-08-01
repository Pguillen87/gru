/*
 * Copyright (C) 2026 Gru Contributors
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 */

package com.pguillen.gru.dictation

enum class TranscriptionEngine {
    ONLINE_GROQ,
    PRIVATE_LOCAL,
}

fun interface GruTranscriptionGatewayFactory {
    fun create(): GruTranscriptionGateway
}

class TranscriptionEngineRouter(
    private val selectedEngine: () -> TranscriptionEngine?,
    private val groqGateway: () -> GruTranscriptionGateway,
    private val localGateway: () -> GruTranscriptionGateway,
) : GruTranscriptionGatewayFactory {
    override fun create(): GruTranscriptionGateway = when (selectedEngine()) {
        TranscriptionEngine.ONLINE_GROQ -> groqGateway()
        TranscriptionEngine.PRIVATE_LOCAL -> localGateway()
        null -> GruTranscriptionGateway {
            throw GruTranscriptionException(GruDictationFailure.ENGINE_NOT_SELECTED)
        }
    }
}

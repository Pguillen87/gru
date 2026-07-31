/*
 * Copyright (C) 2026 Gru Contributors
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 */

package dev.patrickgold.florisboard.gru.dictation

sealed interface GruDictationState {
    data object Idle : GruDictationState

    data class Recording(
        val startedAtMillis: Long,
        val elapsedMillis: Long = 0L,
        val audioLevel: Float = 0f,
    ) : GruDictationState

    data object Transcribing : GruDictationState
    data object Success : GruDictationState
    data class Error(val reason: GruDictationFailure) : GruDictationState
}

enum class GruDictationFailure {
    MICROPHONE_PERMISSION,
    MICROPHONE_UNAVAILABLE,
    NO_SPEECH,
    MISSING_API_KEY,
    NETWORK,
    PROVIDER,
    EMPTY_RESPONSE,
    INSERTION_REJECTED,
    UNKNOWN,
}

/*
 * Copyright (C) 2026 Gru Contributors
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 */

package com.pguillen.gru.dictation

object TranscriptionSelectionPolicy {
    fun engineAfterSelection(
        current: TranscriptionEngine?,
        requested: TranscriptionEngine,
        targetReady: Boolean,
    ): TranscriptionEngine? = when {
        targetReady -> requested
        requested == TranscriptionEngine.PRIVATE_LOCAL -> null
        current == TranscriptionEngine.PRIVATE_LOCAL -> current
        else -> null
    }

    fun recoverPendingSelection(
        current: TranscriptionEngine?,
        requested: TranscriptionEngine?,
        hasGroqKey: Boolean,
        hasLocalModel: Boolean,
        allowLegacyPrivateRecovery: Boolean = false,
    ): TranscriptionEngine? {
        val requestedReady = requested?.let { canActivate(it, hasGroqKey, hasLocalModel) } == true
        if (requested == TranscriptionEngine.PRIVATE_LOCAL) {
            return requested.takeIf { requestedReady }
        }

        val currentReady = current?.let { canActivate(it, hasGroqKey, hasLocalModel) } == true
        if (currentReady) return current

        return when {
            requestedReady -> requested
            requested == TranscriptionEngine.ONLINE_GROQ && hasLocalModel && allowLegacyPrivateRecovery ->
                TranscriptionEngine.PRIVATE_LOCAL
            else -> null
        }
    }

    fun canActivate(
        engine: TranscriptionEngine,
        hasGroqKey: Boolean,
        hasLocalModel: Boolean,
    ): Boolean = when (engine) {
        TranscriptionEngine.ONLINE_GROQ -> hasGroqKey
        TranscriptionEngine.PRIVATE_LOCAL -> hasLocalModel
    }
}

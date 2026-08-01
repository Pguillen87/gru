/*
 * Copyright (C) 2026 Gru Contributors
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 */

package com.pguillen.gru.dictation

object TranscriptionSelectionPolicy {
    fun canActivate(
        engine: TranscriptionEngine,
        hasGroqKey: Boolean,
        hasLocalModel: Boolean,
    ): Boolean = when (engine) {
        TranscriptionEngine.ONLINE_GROQ -> hasGroqKey
        TranscriptionEngine.PRIVATE_LOCAL -> hasLocalModel
    }
}

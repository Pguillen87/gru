/*
 * Copyright (C) 2026 Gru Contributors
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 */

package com.pguillen.gru.dictation

import android.util.Log

internal object GruDiagnostics {
    fun nowMillis(): Long = System.nanoTime() / NANOS_PER_MILLISECOND

    fun info(message: String) {
        runCatching { Log.i(TAG, message) }
    }

    private const val TAG = "GruTranscription"
    private const val NANOS_PER_MILLISECOND = 1_000_000L
}

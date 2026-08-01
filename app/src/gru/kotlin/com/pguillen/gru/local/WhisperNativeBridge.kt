/*
 * Copyright (C) 2026 Gru Contributors
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 */

package com.pguillen.gru.local

internal object WhisperNativeBridge {
    init {
        System.loadLibrary("gru_whisper")
    }

    external fun create(modelPath: String): Long
    external fun transcribe(handle: Long, samples: FloatArray, language: String, threadCount: Int): String
    external fun cancel(handle: Long)
    external fun destroy(handle: Long)
}

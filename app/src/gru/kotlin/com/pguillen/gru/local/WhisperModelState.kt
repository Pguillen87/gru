/*
 * Copyright (C) 2026 Gru Contributors
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 */

package com.pguillen.gru.local

import java.io.File

sealed interface WhisperModelState {
    data object NotInstalled : WhisperModelState
    data object Preparing : WhisperModelState
    data class Downloading(val downloadedBytes: Long, val totalBytes: Long) : WhisperModelState
    data object Verifying : WhisperModelState
    data class Installed(val file: File, val sizeBytes: Long) : WhisperModelState
    data class Error(val reason: WhisperModelError) : WhisperModelState
}

enum class WhisperModelError {
    INSUFFICIENT_SPACE,
    NETWORK,
    INVALID_SIZE,
    INVALID_CHECKSUM,
    STORAGE,
}

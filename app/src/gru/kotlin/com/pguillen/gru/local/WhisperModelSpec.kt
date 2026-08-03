/*
 * Copyright (C) 2026 Gru Contributors
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 */

package com.pguillen.gru.local

data class WhisperModelSpec(
    val id: String,
    val version: String,
    val fileName: String,
    val downloadUrl: String,
    val expectedBytes: Long,
    val sha256: String,
)

object GruWhisperModel {
    val BASE_Q5_1 = WhisperModelSpec(
        id = "base-q5_1",
        version = "ggerganov/whisper.cpp@5359861c739e955e79d9a303bcbc70fb988958b1",
        fileName = "ggml-base-q5_1.bin",
        downloadUrl = "https://huggingface.co/ggerganov/whisper.cpp/resolve/" +
            "5359861c739e955e79d9a303bcbc70fb988958b1/ggml-base-q5_1.bin?download=true",
        expectedBytes = 59_707_625L,
        sha256 = "422f1ae452ade6f30a004d7e5c6a43195e4433bc370bf23fac9cc591f01a8898",
    )
}

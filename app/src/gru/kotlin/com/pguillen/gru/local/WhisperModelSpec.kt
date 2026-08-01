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
    val LARGE_V3_TURBO_Q5_0 = WhisperModelSpec(
        id = "large-v3-turbo-q5_0",
        version = "ggerganov/whisper.cpp@5359861c739e955e79d9a303bcbc70fb988958b1",
        fileName = "ggml-large-v3-turbo-q5_0.bin",
        downloadUrl = "https://huggingface.co/ggerganov/whisper.cpp/resolve/" +
            "5359861c739e955e79d9a303bcbc70fb988958b1/ggml-large-v3-turbo-q5_0.bin?download=true",
        expectedBytes = 574_041_195L,
        sha256 = "394221709cd5ad1f40c46e6031ca61bce88931e6e088c188294c6d5a55ffa7e2",
    )
}

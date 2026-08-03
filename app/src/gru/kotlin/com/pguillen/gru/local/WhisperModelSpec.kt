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
    val SMALL_Q5_1 = WhisperModelSpec(
        id = "small-q5_1",
        version = "ggerganov/whisper.cpp@5359861c739e955e79d9a303bcbc70fb988958b1",
        fileName = "ggml-small-q5_1.bin",
        downloadUrl = "https://huggingface.co/ggerganov/whisper.cpp/resolve/" +
            "5359861c739e955e79d9a303bcbc70fb988958b1/ggml-small-q5_1.bin?download=true",
        expectedBytes = 190_085_487L,
        sha256 = "ae85e4a935d7a567bd102fe55afc16bb595bdb618e11b2fc7591bc08120411bb",
    )
}

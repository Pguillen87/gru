/*
 * Copyright (C) 2026 Gru Contributors
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 */

package com.pguillen.gru.local

import java.io.File
import java.io.FileOutputStream
import java.io.IOException
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.suspendCancellableCoroutine
import okhttp3.Call
import okhttp3.Callback
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response

class WhisperModelDownloader(private val client: OkHttpClient) {
    suspend fun download(spec: WhisperModelSpec, target: File, onProgress: (Long) -> Unit) {
        target.parentFile?.mkdirs()
        val existing = target.length().takeIf { target.isFile && it in 1 until spec.expectedBytes } ?: 0L
        val request = Request.Builder().url(spec.downloadUrl).apply {
            if (existing > 0L) header("Range", "bytes=$existing-")
        }.build()
        execute(request).use { response ->
            if (!response.isSuccessful) throw IOException("Model download HTTP ${response.code}")
            val append = existing > 0L && response.code == HTTP_PARTIAL
            val start = if (append) existing else 0L
            if (!append && target.exists()) target.delete()
            writeResponse(response, target, append, start, onProgress)
        }
    }

    private suspend fun writeResponse(
        response: Response,
        target: File,
        append: Boolean,
        start: Long,
        onProgress: (Long) -> Unit,
    ) {
        response.body.byteStream().use { input ->
            FileOutputStream(target, append).buffered().use { output ->
                copy(input, output, start, onProgress)
            }
        }
    }

    private suspend fun copy(
        input: java.io.InputStream,
        output: java.io.OutputStream,
        start: Long,
        onProgress: (Long) -> Unit,
    ) {
        var downloaded = start
        val buffer = ByteArray(BUFFER_BYTES)
        while (true) {
            kotlinx.coroutines.currentCoroutineContext().ensureActive()
            val read = input.read(buffer)
            if (read < 0) break
            output.write(buffer, 0, read)
            downloaded += read
            onProgress(downloaded)
        }
    }

    private suspend fun execute(request: Request): Response = suspendCancellableCoroutine { continuation ->
        val call = client.newCall(request)
        continuation.invokeOnCancellation { call.cancel() }
        call.enqueue(object : Callback {
            override fun onFailure(call: Call, e: IOException) {
                if (continuation.isActive) continuation.resumeWithException(e)
            }

            override fun onResponse(call: Call, response: Response) {
                if (continuation.isActive) continuation.resume(response) else response.close()
            }
        })
    }

    private companion object {
        const val HTTP_PARTIAL = 206
        const val BUFFER_BYTES = 128 * 1024
    }
}

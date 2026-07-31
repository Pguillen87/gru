/*
 * Copyright (C) 2026 Gru Contributors
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 */

package com.pguillen.gru.dictation

import java.io.File
import java.io.IOException
import java.util.concurrent.TimeUnit
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import okhttp3.Call
import okhttp3.Callback
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.asRequestBody
import okhttp3.Response

internal class GroqTranscriptionClient(
    private val client: OkHttpClient = defaultClient,
    private val endpoint: String = GROQ_TRANSCRIPTION_URL,
) {
    suspend fun transcribe(audioFile: File, apiKey: String, model: String): String {
        val request = Request.Builder()
            .url(endpoint)
            .header("Authorization", "Bearer $apiKey")
            .post(
                MultipartBody.Builder()
                    .setType(MultipartBody.FORM)
                    .addFormDataPart(
                        "file",
                        audioFile.name,
                        audioFile.asRequestBody(WAV_MEDIA_TYPE),
                    )
                    .addFormDataPart("model", model)
                    .addFormDataPart("response_format", "json")
                    .build(),
            )
            .build()
        return execute(request).use { response ->
            val body = response.body.string()
            if (!response.isSuccessful) {
                throw GroqProviderException(response.code)
            }
            parseText(body)
        }
    }

    private suspend fun execute(request: Request): Response = suspendCancellableCoroutine { continuation ->
        val call = client.newCall(request)
        continuation.invokeOnCancellation { call.cancel() }
        call.enqueue(object : Callback {
            override fun onFailure(call: Call, error: IOException) {
                if (continuation.isActive) continuation.resumeWithException(error)
            }

            override fun onResponse(call: Call, response: Response) {
                if (continuation.isActive) continuation.resume(response) else response.close()
            }
        })
    }

    internal fun parseText(body: String): String =
        Json.parseToJsonElement(body).jsonObject["text"]?.jsonPrimitive?.content.orEmpty().trim()

    private companion object {
        const val GROQ_TRANSCRIPTION_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
        val WAV_MEDIA_TYPE = "audio/wav".toMediaType()
        val defaultClient = OkHttpClient.Builder()
            .connectTimeout(15, TimeUnit.SECONDS)
            .readTimeout(120, TimeUnit.SECONDS)
            .writeTimeout(120, TimeUnit.SECONDS)
            .build()
    }
}

internal class GroqProviderException(val statusCode: Int) : IOException()

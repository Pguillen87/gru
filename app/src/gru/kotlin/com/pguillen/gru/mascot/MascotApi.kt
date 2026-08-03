package com.pguillen.gru.mascot

import com.pguillen.gru.BuildConfig
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.util.Base64

data class RemoteMascotJob(val id: String, val state: String, val masterIds: List<String> = emptyList())

class MascotApi(
    private val tokens: MascotAuthTokenProvider,
    private val client: OkHttpClient = OkHttpClient(),
    private val baseUrl: String = BuildConfig.MASCOT_API_BASE_URL,
) {
    suspend fun createJob(image: ByteArray, mimeType: String, idempotencyKey: String): RemoteMascotJob = request(
        path = "/v1/mascot/jobs", method = "POST", idempotencyKey = idempotencyKey,
        body = "{\"image_base64\":\"${Base64.getEncoder().encodeToString(image)}\",\"content_type\":\"$mimeType\"}",
    )

    suspend fun job(jobId: String): RemoteMascotJob = request("/v1/mascot/jobs/$jobId", "GET")

    suspend fun approveMaster(jobId: String, masterId: String, idempotencyKey: String): RemoteMascotJob = request(
        "/v1/mascot/jobs/$jobId/approve-master", "POST", idempotencyKey,
        "{\"master_id\":\"$masterId\"}",
    )

    private suspend fun request(path: String, method: String, idempotencyKey: String? = null, body: String? = null): RemoteMascotJob = withContext(Dispatchers.IO) {
        val builder = Request.Builder().url(baseUrl.trimEnd('/') + path)
            .header("Authorization", "Bearer ${tokens.token()}")
        idempotencyKey?.let { builder.header("X-Idempotency-Key", it) }
        val request = when (method) {
            "GET" -> builder.get().build()
            else -> builder.method(method, (body ?: "{}").toRequestBody(JSON)).build()
        }
        client.newCall(request).execute().use { response ->
            if (!response.isSuccessful) throw MascotApiException("Não foi possível continuar a criação do mascote.")
            val json = Json.parseToJsonElement(response.body.string()).jsonObject
            RemoteMascotJob(
                id = json["job_id"]?.jsonPrimitive?.content ?: throw MascotApiException("Resposta inválida do serviço."),
                state = json["state"]?.jsonPrimitive?.content ?: "QUEUED",
                masterIds = json["masters"]?.let { element -> element.jsonObject.keys.toList() } ?: emptyList(),
            )
        }
    }

    private companion object { val JSON = "application/json; charset=utf-8".toMediaType() }
}

class MascotApiException(message: String) : Exception(message)

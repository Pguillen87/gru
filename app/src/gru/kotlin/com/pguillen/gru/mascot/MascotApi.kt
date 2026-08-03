package com.pguillen.gru.mascot

import com.pguillen.gru.BuildConfig
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.util.Base64

data class CreateMascotJobRequest(val imageBase64: String, val contentType: String) {
    fun json(): JsonObject = buildJsonObject {
        put("image_base64", JsonPrimitive(imageBase64)); put("content_type", JsonPrimitive(contentType))
    }
}

data class ApproveMasterRequest(val masterId: String) {
    fun json(): JsonObject = buildJsonObject { put("master_id", JsonPrimitive(masterId)) }
}

data class MascotJobResponse(val jobId: String, val state: String, val masterIds: List<String>) {
    companion object {
        fun from(json: JsonObject) = MascotJobResponse(
            jobId = json["job_id"]?.jsonPrimitive?.content ?: throw MascotApiException(ApiError("INVALID_RESPONSE", "Resposta inválida do serviço.")),
            state = json["state"]?.jsonPrimitive?.content ?: "QUEUED",
            masterIds = json["masters"]?.jsonObject?.keys?.toList().orEmpty(),
        )
    }
}

data class ApiError(val code: String, val message: String) {
    companion object {
        fun from(body: String): ApiError? = runCatching {
            val detail = Json.parseToJsonElement(body).jsonObject["detail"]?.jsonObject ?: return null
            ApiError(detail["code"]?.jsonPrimitive?.content ?: "UNKNOWN", detail["message"]?.jsonPrimitive?.content ?: "")
        }.getOrNull()
    }
}

class MascotApi(
    private val tokens: MascotAuthTokenProvider,
    private val appCheck: MascotAppCheckTokenProvider,
    private val client: OkHttpClient = OkHttpClient(),
    private val baseUrl: String = BuildConfig.MASCOT_API_BASE_URL,
) {
    suspend fun createJob(image: ByteArray, mimeType: String, idempotencyKey: String): MascotJobResponse = request(
        "/v1/mascot/jobs", "POST", idempotencyKey,
        CreateMascotJobRequest(Base64.getEncoder().encodeToString(image), mimeType).json(),
    )

    suspend fun job(jobId: String): MascotJobResponse = request("/v1/mascot/jobs/$jobId", "GET")

    suspend fun approveMaster(jobId: String, masterId: String, idempotencyKey: String): MascotJobResponse = request(
        "/v1/mascot/jobs/$jobId/approve-master", "POST", idempotencyKey, ApproveMasterRequest(masterId).json(),
    )

    private suspend fun request(path: String, method: String, idempotencyKey: String? = null, body: JsonObject? = null): MascotJobResponse = withContext(Dispatchers.IO) {
        val builder = Request.Builder().url(baseUrl.trimEnd('/') + path)
            .header("Authorization", "Bearer ${tokens.token()}")
            .header("X-Firebase-AppCheck", appCheck.token())
        idempotencyKey?.let { builder.header("X-Idempotency-Key", it) }
        val request = if (method == "GET") builder.get().build() else builder.method(method, Json.encodeToString(JsonObject.serializer(), body ?: buildJsonObject {}).toRequestBody(JSON)).build()
        client.newCall(request).execute().use { response ->
            val responseBody = response.body.string()
            if (!response.isSuccessful) throw MascotApiException(ApiError.from(responseBody) ?: ApiError("HTTP_${response.code}", ""))
            MascotJobResponse.from(Json.parseToJsonElement(responseBody).jsonObject)
        }
    }

    private companion object { val JSON = "application/json; charset=utf-8".toMediaType() }
}

class MascotApiException(val apiError: ApiError) : Exception(apiError.message)

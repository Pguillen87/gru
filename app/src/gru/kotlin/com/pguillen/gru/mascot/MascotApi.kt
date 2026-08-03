package com.pguillen.gru.mascot

import com.pguillen.gru.BuildConfig
import java.util.Base64
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody

data class CreateMascotJobRequest(val imageBase64: String, val contentType: String) {
    fun json(): JsonObject = buildJsonObject {
        put("image_base64", JsonPrimitive(imageBase64))
        put("content_type", JsonPrimitive(contentType))
    }
}

data class ApproveMasterRequest(val masterId: String) {
    fun json(): JsonObject = buildJsonObject { put("master_id", JsonPrimitive(masterId)) }
}

data class MasterReference(
    val id: String,
    val downloadPath: String,
    val sha256: String? = null,
)

data class MascotJobResponse(
    val jobId: String,
    val state: String,
    val masters: List<MasterReference> = emptyList(),
) {
    companion object {
        fun from(json: JsonObject) = MascotJobResponse(
            jobId = json.requiredString("job_id"),
            state = json.string("state") ?: "QUEUED",
            masters = json["masters"]?.jsonArray?.map { item ->
                val master = item.jsonObject
                MasterReference(master.requiredString("id"), master.requiredString("download_path"), master.string("sha256"))
            }.orEmpty(),
        )
    }
}

data class MascotResultResponse(
    val poseSetId: String,
    val masterId: String,
    val version: String,
    val modelVersion: String?,
    val poses: List<MascotPose>,
) {
    companion object {
        fun from(json: JsonObject) = MascotResultResponse(
            poseSetId = json.requiredString("poseSetId"), masterId = json.requiredString("masterId"),
            version = json.requiredString("version"), modelVersion = json.string("modelVersion"),
            poses = json["poses"]?.jsonArray?.map { item -> item.jsonObject.let { pose ->
                MascotPose(
                    pose.requiredString("poseId"), pose.requiredString("name"), pose.requiredString("fileName"),
                    pose.requiredString("sha256"), pose.requiredString("downloadPath"),
                )
            } }.orEmpty(),
        )
    }
}

data class ApiError(val code: String, val message: String) {
    companion object {
        fun from(body: String): ApiError? = runCatching {
            val detail = Json.parseToJsonElement(body).jsonObject["detail"]?.jsonObject ?: return null
            ApiError(detail.string("code") ?: "UNKNOWN", detail.string("message").orEmpty())
        }.getOrNull()
    }
}

interface MascotRemoteApi {
    suspend fun createJob(image: ByteArray, mimeType: String, key: String): MascotJobResponse
    suspend fun job(jobId: String): MascotJobResponse
    suspend fun recoverJob(idempotencyKey: String): MascotJobResponse
    suspend fun startMasterGeneration(jobId: String, key: String): MascotJobResponse
    suspend fun approveMaster(jobId: String, masterId: String, key: String): MascotJobResponse
    suspend fun cancel(jobId: String, key: String): MascotJobResponse
    suspend fun result(jobId: String): MascotResultResponse
    suspend fun download(path: String): ByteArray
}

class MascotApi(
    private val tokens: MascotAuthTokenProvider,
    private val appCheck: MascotAppCheckTokenProvider,
    private val client: OkHttpClient = mascotHttpClient(),
    private val baseUrl: String = BuildConfig.MASCOT_API_BASE_URL,
) : MascotRemoteApi {
    override suspend fun createJob(image: ByteArray, mimeType: String, key: String): MascotJobResponse {
        val started = MascotTelemetry.mark()
        MascotTelemetry.info(
            "create_prepare",
            fields = mapOf("image_bytes" to image.size, "content_type" to mimeType, "correlation" to MascotTelemetry.correlation(key)),
        )
        return runCatching {
            requestJob(
                "/v1/mascot/jobs", "POST", key,
                CreateMascotJobRequest(Base64.getEncoder().encodeToString(image), mimeType).json(),
            )
        }.onSuccess { job ->
            MascotTelemetry.info("create_complete", started, mapOf("remote_state" to job.state))
        }.onFailure { error ->
            MascotTelemetry.failure("create_complete", started, error)
        }.getOrThrow()
    }

    override suspend fun job(jobId: String): MascotJobResponse = requestJob("/v1/mascot/jobs/$jobId", "GET")

    override suspend fun recoverJob(idempotencyKey: String): MascotJobResponse = requestJob(
        "/v1/mascot/idempotency/${idempotencyKey.requireSafeIdentifier()}", "GET",
    )

    override suspend fun startMasterGeneration(jobId: String, key: String): MascotJobResponse = requestJob(
        "/v1/mascot/jobs/$jobId/generate-master", "POST", key, buildJsonObject {},
    )

    override suspend fun approveMaster(jobId: String, masterId: String, key: String): MascotJobResponse = requestJob(
        "/v1/mascot/jobs/$jobId/approve-master", "POST", key, ApproveMasterRequest(masterId).json(),
    )

    override suspend fun cancel(jobId: String, key: String): MascotJobResponse =
        requestJob("/v1/mascot/jobs/$jobId/cancel", "POST", key, buildJsonObject {})

    override suspend fun result(jobId: String): MascotResultResponse = MascotResultResponse.from(
        requestJson("/v1/mascot/jobs/$jobId/result", "GET"),
    )

    override suspend fun download(path: String): ByteArray = withContext(Dispatchers.IO) {
        require(path.startsWith("/v1/mascot/jobs/") && ".." !in path && '?' !in path && '#' !in path) {
            "Untrusted mascot download path."
        }
        client.newCall(authenticatedRequest(path).get().build()).execute().use { response ->
            val bytes = response.body.bytes()
            if (!response.isSuccessful) throw response.toMascotApiException(bytes.decodeToString())
            bytes
        }
    }

    private suspend fun requestJob(path: String, method: String, key: String? = null, body: JsonObject? = null) =
        MascotJobResponse.from(requestJson(path, method, key, body))

    private suspend fun requestJson(path: String, method: String, key: String? = null, body: JsonObject? = null): JsonObject =
        withContext(Dispatchers.IO) {
            val started = MascotTelemetry.mark()
            val operation = operationName(path, method)
            try {
                executeJson(path, method, key, body, started, operation)
            } catch (error: Exception) {
                MascotTelemetry.failure("http_complete", started, error, mapOf("operation" to operation))
                throw error
            }
        }

    private suspend fun executeJson(
        path: String, method: String, key: String?, body: JsonObject?, started: Long, operation: String,
    ): JsonObject {
        val payload = body?.let { Json.encodeToString(JsonObject.serializer(), it) }
        val builder = authenticatedRequest(path)
        key?.let { builder.header("X-Idempotency-Key", it) }
        val request = if (method == "GET") builder.get().build() else builder.method(
            method, (payload ?: "{}").toRequestBody(JSON_MEDIA),
        ).build()
        return client.newCall(request).execute().use { response ->
            val responseBody = response.body.string()
            if (!response.isSuccessful) throw response.toMascotApiException(responseBody)
            MascotTelemetry.info(
                "http_complete", started,
                mapOf("operation" to operation, "outcome" to "success", "http_status" to response.code,
                    "payload_bytes" to (payload?.toByteArray()?.size ?: 0), "response_bytes" to responseBody.toByteArray().size,
                    "request_id" to response.header("X-Request-ID")),
            )
            Json.parseToJsonElement(responseBody).jsonObject
        }
    }

    private suspend fun authenticatedRequest(path: String): Request.Builder = Request.Builder()
        .url(baseUrl.trimEnd('/') + path)
        .header("Authorization", "Bearer ${tokens.token()}")
        .header("X-Firebase-AppCheck", appCheck.token())

    private companion object { val JSON_MEDIA = "application/json; charset=utf-8".toMediaType() }
}

private fun mascotHttpClient(): OkHttpClient = OkHttpClient.Builder()
    .connectTimeout(20, TimeUnit.SECONDS)
    .writeTimeout(30, TimeUnit.SECONDS)
    .readTimeout(60, TimeUnit.SECONDS)
    .callTimeout(75, TimeUnit.SECONDS)
    .build()

class MascotApiException(
    val apiError: ApiError,
    val httpStatus: Int? = null,
    val requestId: String? = null,
) : Exception(apiError.message)

private fun okhttp3.Response.toMascotApiException(body: String): MascotApiException {
    val fallback = if (code >= 500) "SERVICE_UNAVAILABLE" else "HTTP_$code"
    return MascotApiException(ApiError.from(body) ?: ApiError(fallback, ""), code, header("X-Request-ID"))
}

private fun operationName(path: String, method: String): String = when {
    path == "/v1/mascot/jobs" -> "create"
    "/idempotency/" in path -> "recover"
    path.endsWith("/approve-master") -> "approve"
    path.endsWith("/generate-master") -> "generate_master"
    path.endsWith("/cancel") -> "cancel"
    path.endsWith("/result") -> "result"
    "/masters/" in path -> "download_master"
    "/poses/" in path -> "download_pose"
    method == "GET" -> "read_job"
    else -> "unknown"
}

private fun JsonObject.string(key: String): String? = this[key]?.jsonPrimitive?.content
private fun String.requireSafeIdentifier(): String = also {
    require(matches(Regex("^[A-Za-z0-9:_-]{1,160}$"))) { "Invalid mascot identifier." }
}
private fun JsonObject.requiredString(key: String): String = string(key)
    ?: throw MascotApiException(ApiError("INVALID_RESPONSE", "Resposta inválida do serviço."))

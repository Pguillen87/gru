package com.pguillen.gru.mascot

import android.util.Log
import java.security.MessageDigest

internal object MascotTelemetry {
    private const val TAG = "GruMascot"

    fun mark(): Long = System.nanoTime()

    fun info(event: String, startedAt: Long? = null, fields: Map<String, Any?> = emptyMap()) {
        write(Log.INFO, event, startedAt, fields)
    }

    fun failure(event: String, startedAt: Long, error: Throwable, fields: Map<String, Any?> = emptyMap()) {
        val apiError = error as? MascotApiException
        write(
            Log.WARN,
            event,
            startedAt,
            fields + mapOf(
                "outcome" to "failure",
                "error_class" to error.javaClass.simpleName,
                "api_code" to apiError?.apiError?.code,
                "http_status" to apiError?.httpStatus,
                "request_id" to apiError?.requestId,
            ),
        )
    }

    fun correlation(value: String): String = MessageDigest.getInstance("SHA-256")
        .digest(value.toByteArray())
        .take(6)
        .joinToString("") { "%02x".format(it) }

    private fun write(priority: Int, event: String, startedAt: Long?, fields: Map<String, Any?>) {
        val duration = startedAt?.let { (System.nanoTime() - it).coerceAtLeast(0) / 1_000_000 }
        val values = linkedMapOf<String, Any?>("event" to event, "duration_ms" to duration).apply { putAll(fields) }
        val message = values.entries
            .filter { it.value != null }
            .joinToString(" ") { (key, value) -> "${safe(key)}=${safe(value.toString())}" }
        runCatching { Log.println(priority, TAG, message) }
    }

    internal fun safe(value: String): String = value
        .replace(Regex("[^A-Za-z0-9._:-]"), "_")
        .take(80)
}

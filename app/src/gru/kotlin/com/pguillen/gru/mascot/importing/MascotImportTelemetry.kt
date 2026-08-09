package com.pguillen.gru.mascot.importing

import android.os.SystemClock
import android.util.Log
import java.util.UUID

internal object MascotImportTelemetry {
    private const val TAG = "GruPerch"
    @Volatile private var traceId: String? = null

    fun begin(): Long {
        traceId = UUID.randomUUID().toString().replace("-", "").take(8)
        event("import_started")
        return mark()
    }

    fun mark(): Long = runCatching { SystemClock.elapsedRealtime() }.getOrElse { System.nanoTime() / 1_000_000L }

    fun event(name: String, startedAt: Long? = null, fields: Map<String, Any?> = emptyMap()) {
        val values = linkedMapOf<String, Any?>("event" to name, "trace_id" to traceId)
        startedAt?.let { values["duration_ms"] = (mark() - it).coerceAtLeast(0) }
        values.putAll(fields)
        val message = values.filterValues { it != null }.entries.joinToString(" ") { (key, value) ->
            "${safe(key)}=${safe(value.toString())}"
        }
        runCatching { Log.i(TAG, message) }
    }

    private fun safe(value: String): String = value.replace(Regex("[^A-Za-z0-9._:-]"), "_").take(64)
}

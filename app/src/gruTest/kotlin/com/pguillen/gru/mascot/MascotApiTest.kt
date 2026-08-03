package com.pguillen.gru.mascot

import kotlinx.coroutines.test.runTest
import okhttp3.OkHttpClient
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertTrue

class MascotApiTest {
    @Test fun `serializes request and sends proof headers`() = runTest {
        val server = MockWebServer().apply { enqueue(MockResponse().setResponseCode(202).setBody("{\"job_id\":\"job_1\",\"state\":\"QUEUED\"}")); start() }
        try {
            val api = MascotApi(FakeAuth, FakeAppCheck, OkHttpClient(), server.url("/").toString())
            assertEquals("job_1", api.createJob(byteArrayOf(1, 2), "image/png", "request-1").jobId)
            val request = server.takeRequest()
            assertEquals("Bearer test-id-token", request.getHeader("Authorization"))
            assertEquals("test-app-check", request.getHeader("X-Firebase-AppCheck"))
            assertEquals("request-1", request.getHeader("X-Idempotency-Key"))
            assertTrue(request.body.readUtf8().contains("image_base64"))
        } finally { server.shutdown() }
    }

    @Test fun `maps structured API failure`() = runTest {
        val server = MockWebServer().apply {
            enqueue(MockResponse().setResponseCode(429).setHeader("X-Request-ID", "trace-123").setBody("{\"detail\":{\"code\":\"RATE_LIMITED\",\"message\":\"later\",\"retry_at_utc\":\"2026-08-04T00:00:00Z\",\"charge_incurred\":false}}"))
            start()
        }
        try {
            val api = MascotApi(FakeAuth, FakeAppCheck, OkHttpClient(), server.url("/").toString())
            val error = assertFailsWith<MascotApiException> { api.job("job_1") }
            assertEquals("RATE_LIMITED", error.apiError.code)
            assertEquals("2026-08-04T00:00:00Z", error.apiError.retryAtUtc)
            assertEquals(false, error.apiError.chargeIncurred)
            assertEquals("trace-123", error.requestId)
        } finally { server.shutdown() }
    }

    @Test fun `telemetry sanitizes values and hashes correlation keys`() {
        assertEquals("value_with_token", MascotTelemetry.safe("value with/token"))
        assertEquals(MascotTelemetry.correlation("request-1"), MascotTelemetry.correlation("request-1"))
        assertTrue(MascotTelemetry.correlation("request-1") != MascotTelemetry.correlation("request-2"))
    }

    @Test fun `photo dimensions preserve aspect ratio within server limit`() {
        assertEquals(4096 to 2048, scaledSize(8000, 4000))
        assertEquals(2048 to 4096, scaledSize(3000, 6000))
        assertEquals(1200 to 900, scaledSize(1200, 900))
    }

    @Test fun `maps backend failure separately from network failure`() = runTest {
        val server = MockWebServer().apply { enqueue(MockResponse().setResponseCode(503).setBody("unavailable")); start() }
        try {
            val api = MascotApi(FakeAuth, FakeAppCheck, OkHttpClient(), server.url("/").toString())
            val error = assertFailsWith<MascotApiException> { api.job("job_1") }
            assertEquals("SERVICE_UNAVAILABLE", error.apiError.code)
            assertEquals(503, error.httpStatus)
            assertEquals(
                "O serviço de mascotes está temporariamente indisponível. Tente novamente mais tarde.",
                mascotErrorMessage(error),
            )
        } finally { server.shutdown() }
    }

    @Test fun `recovers a create by stable idempotency key`() = runTest {
        val server = MockWebServer().apply { enqueue(MockResponse().setBody("{\"job_id\":\"job_1\",\"state\":\"READY_FOR_GENERATION\"}")); start() }
        try {
            val api = MascotApi(FakeAuth, FakeAppCheck, OkHttpClient(), server.url("/").toString())
            assertEquals("job_1", api.recoverJob("request-1").jobId)
            assertEquals("/v1/mascot/idempotency/request-1", server.takeRequest().path)
        } finally { server.shutdown() }
    }

    @Test fun `starts a paused Master with proof and idempotency headers`() = runTest {
        val server = MockWebServer().apply {
            enqueue(MockResponse().setResponseCode(202).setBody("{\"job_id\":\"job_1\",\"state\":\"VALIDATING_INPUT\"}"))
            start()
        }
        try {
            val api = MascotApi(FakeAuth, FakeAppCheck, OkHttpClient(), server.url("/").toString())
            assertEquals("VALIDATING_INPUT", api.startMasterGeneration("job_1", "generate-master:job_1").state)
            val request = server.takeRequest()
            assertEquals("/v1/mascot/jobs/job_1/generate-master", request.path)
            assertEquals("generate-master:job_1", request.getHeader("X-Idempotency-Key"))
            assertEquals("Bearer test-id-token", request.getHeader("Authorization"))
            assertEquals("test-app-check", request.getHeader("X-Firebase-AppCheck"))
        } finally { server.shutdown() }
    }

    @Test fun `parses typed master references and downloads with proof headers`() = runTest {
        val body = """{"job_id":"job_1","state":"AWAITING_MASTER_APPROVAL","masters":[{"id":"master_1","download_path":"/v1/mascot/jobs/job_1/masters/master_1","sha256":"abc"}]}"""
        val server = MockWebServer().apply {
            enqueue(MockResponse().setBody(body)); enqueue(MockResponse().setBody("image-bytes")); start()
        }
        try {
            val api = MascotApi(FakeAuth, FakeAppCheck, OkHttpClient(), server.url("/").toString())
            val master = api.job("job_1").masters.single()
            assertEquals("master_1", master.id)
            assertEquals("abc", master.sha256)
            assertEquals("image-bytes", api.download(master.downloadPath).decodeToString())
            val download = server.takeRequest().let { server.takeRequest() }
            assertEquals("Bearer test-id-token", download.getHeader("Authorization"))
            assertEquals("test-app-check", download.getHeader("X-Firebase-AppCheck"))
        } finally { server.shutdown() }
    }

    @Test fun `rejects an untrusted server download path`() = runTest {
        val api = MascotApi(FakeAuth, FakeAppCheck, OkHttpClient(), "https://example.invalid")
        assertFailsWith<IllegalArgumentException> { api.download("https://attacker.invalid/file") }
    }

    private data object FakeAuth : MascotAuthTokenProvider { override suspend fun token() = "test-id-token" }
    private data object FakeAppCheck : MascotAppCheckTokenProvider { override suspend fun token() = "test-app-check" }
}

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
        val server = MockWebServer().apply { enqueue(MockResponse().setResponseCode(429).setBody("{\"detail\":{\"code\":\"RATE_LIMITED\",\"message\":\"later\"}}")); start() }
        try {
            val api = MascotApi(FakeAuth, FakeAppCheck, OkHttpClient(), server.url("/").toString())
            assertEquals("RATE_LIMITED", assertFailsWith<MascotApiException> { api.job("job_1") }.apiError.code)
        } finally { server.shutdown() }
    }

    private data object FakeAuth : MascotAuthTokenProvider { override suspend fun token() = "test-id-token" }
    private data object FakeAppCheck : MascotAppCheckTokenProvider { override suspend fun token() = "test-app-check" }
}

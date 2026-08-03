package com.pguillen.gru.mascot

import java.io.IOException
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.test.runTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class MascotRepositoryTest {
    @Test fun `active pending job blocks a second create`() = runTest {
        val remote = FakeRemote(jobResponse = MascotJobResponse("job-existing", "READY_FOR_GENERATION"))
        val pending = FakePending("job-existing")
        val result = MascotRepository(remote, pending).create(byteArrayOf(1), "image/png")
        assertEquals("job-existing", result.jobId)
        assertEquals(0, remote.createCalls)
    }

    @Test fun `network failure keeps pending job and does not create another`() = runTest {
        val remote = FakeRemote(jobFailure = IOException("offline"))
        val pending = FakePending("job-existing")
        assertFailsWith<IOException> { MascotRepository(remote, pending).create(byteArrayOf(1), "image/png") }
        assertEquals("job-existing", pending.jobId.value)
        assertEquals(0, remote.createCalls)
    }

    @Test fun `approval retries use the same deterministic operation key`() = runTest {
        val remote = FakeRemote(jobResponse = MascotJobResponse("job-1", "CONSISTENCY_TEST"))
        val repository = MascotRepository(remote, FakePending("job-1"))
        repository.approve("job-1", "master_2")
        repository.approve("job-1", "master_2")
        assertEquals(listOf("approve:job-1:master_2", "approve:job-1:master_2"), remote.approvalKeys)
    }

    @Test fun `lost create response is recovered by persisted idempotency key`() = runTest {
        val remote = FakeRemote(jobResponse = MascotJobResponse("job-recovered", "READY_FOR_GENERATION"))
        val pending = FakePending().apply { requestId.value = "request-stable" }
        val recovered = MascotRepository(remote, pending).resume()
        assertEquals("job-recovered", recovered?.jobId)
        assertEquals("request-stable", remote.recoveryKeys.single())
        assertEquals("job-recovered", pending.jobId.value)
        assertEquals(null, pending.requestId.value)
    }

    @Test fun `cancel stays pending until remote confirms canceled`() = runTest {
        val pending = FakePending("job-1")
        val remote = FakeRemote(jobResponse = MascotJobResponse("job-1", "READY_FOR_GENERATION"))
        MascotRepository(remote, pending).cancel("job-1")
        assertTrue(pending.cancelPending.value)
        assertEquals("job-1", pending.jobId.value)
        remote.jobResponse = MascotJobResponse("job-1", "CANCELED")
        MascotRepository(remote, pending).cancel("job-1")
        assertFalse(pending.cancelPending.value)
        assertEquals(null, pending.jobId.value)
        assertEquals(listOf("cancel:job-1", "cancel:job-1"), remote.cancelKeys)
    }
}

private class FakePending(initialJobId: String? = null) : MascotPendingState {
    override val jobId = MutableStateFlow(initialJobId)
    override val requestId = MutableStateFlow<String?>(null)
    override val cancelPending = MutableStateFlow(false)
    override fun setJobId(value: String?) { jobId.value = value }
    override fun setRequestId(value: String?) { requestId.value = value }
    override fun setCancelPending(value: Boolean) { cancelPending.value = value }
    override fun selectCustomMascot(poseSetId: String, masterId: String) = Unit
}

private class FakeRemote(
    var jobResponse: MascotJobResponse = MascotJobResponse("job-default", "READY_FOR_GENERATION"),
    var jobFailure: Throwable? = null,
) : MascotRemoteApi {
    var createCalls = 0
    val approvalKeys = mutableListOf<String>()
    val cancelKeys = mutableListOf<String>()
    val recoveryKeys = mutableListOf<String>()

    override suspend fun createJob(image: ByteArray, mimeType: String, key: String): MascotJobResponse {
        createCalls += 1
        return jobResponse
    }
    override suspend fun job(jobId: String): MascotJobResponse = jobFailure?.let { throw it } ?: jobResponse
    override suspend fun recoverJob(idempotencyKey: String): MascotJobResponse {
        recoveryKeys += idempotencyKey
        return jobFailure?.let { throw it } ?: jobResponse
    }
    override suspend fun approveMaster(jobId: String, masterId: String, key: String): MascotJobResponse {
        approvalKeys += key
        return jobResponse
    }
    override suspend fun cancel(jobId: String, key: String): MascotJobResponse {
        cancelKeys += key
        return jobResponse
    }
    override suspend fun result(jobId: String) = error("unused")
    override suspend fun download(path: String) = error("unused")
}

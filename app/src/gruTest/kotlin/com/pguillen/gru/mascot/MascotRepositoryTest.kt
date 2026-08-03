package com.pguillen.gru.mascot

import java.io.IOException
import java.nio.file.Files
import java.security.MessageDigest
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

    @Test fun `only real IO failure is presented as a connection interruption`() {
        assertEquals(
            MascotCreationState.NetworkUnavailable("job-1"),
            IOException("offline").toMascotFailure("job-1"),
        )
        val backend = MascotApiException(ApiError("SERVICE_UNAVAILABLE", ""), 503).toMascotFailure("job-1")
        assertTrue(backend is MascotCreationState.RemoteFailed)
        assertTrue(backend.message.contains("serviço"))
        assertEquals(MascotFailureRecovery.RETRY, backend.recovery)
    }

    @Test fun `firebase configuration failure is not presented as internet failure`() {
        val state = MascotFirebaseConfigurationException(IllegalStateException("missing app")).toMascotFailure(null)
        assertTrue(state is MascotCreationState.RemoteFailed)
        assertTrue(state.message.contains("configurada"))
        assertEquals(MascotFailureRecovery.RETRY, state.recovery)
    }

    @Test fun `invalid photo failure offers choosing another photo`() {
        val state = MascotApiException(ApiError("INVALID_IMAGE", "")).toMascotFailure(null)
        assertTrue(state is MascotCreationState.RemoteFailed)
        assertEquals(MascotFailureRecovery.CHOOSE_PHOTO, state.recovery)
    }

    @Test fun `local photo preparation failure offers choosing another photo`() {
        val state = MascotPhotoPreparationException(IllegalArgumentException()).toMascotFailure(null)
        assertTrue(state is MascotCreationState.RemoteFailed)
        assertTrue(state.message.contains("foto"))
        assertEquals(MascotFailureRecovery.CHOOSE_PHOTO, state.recovery)
    }

    @Test fun `approval retries use the same deterministic operation key`() = runTest {
        val remote = FakeRemote(jobResponse = MascotJobResponse("job-1", "CONSISTENCY_TEST"))
        val repository = MascotRepository(remote, FakePending("job-1"))
        repository.approve("job-1", "master_2")
        repository.approve("job-1", "master_2")
        assertEquals(listOf("approve:job-1:master_2", "approve:job-1:master_2"), remote.approvalKeys)
    }

    @Test fun `approved Master is downloaded promoted selected and remains pending for poses`() = runTest {
        val root = Files.createTempDirectory("gru-approved-master-test").toFile()
        try {
            val bytes = "transparent-master".encodeToByteArray()
            val checksum = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }
            val job = MascotJobResponse(
                "job-1", "CONSISTENCY_TEST",
                masters = listOf(MasterReference("master_2", "/masters/master_2", checksum)),
                masterId = "master_2",
            )
            val pending = FakePending("job-1")
            val repository = MascotRepository(FakeRemote(jobResponse = job, downloadBytes = bytes), pending, CustomMascotStore(root))

            val response = repository.approve("job-1", "master_2")

            assertEquals(job, response)
            assertEquals("job-1" to "master_2", pending.selectedMascot)
            assertEquals("job-1", pending.jobId.value)
            assertEquals("transparent-master", CustomMascotStore(root).previewFile("job-1")?.readText())
        } finally { root.deleteRecursively() }
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

    @Test fun `confirmed missing create clears orphaned request`() = runTest {
        val pending = FakePending().apply { requestId.value = "request-orphaned" }
        val remote = FakeRemote(
            recoveryFailure = MascotApiException(ApiError("JOB_NOT_FOUND", ""), 404),
        )

        assertEquals(null, MascotRepository(remote, pending).resume())
        assertEquals(null, pending.requestId.value)
        assertEquals(0, remote.createCalls)
    }

    @Test fun `retry after confirmed missing create submits exactly once`() = runTest {
        val pending = FakePending().apply { requestId.value = "request-orphaned" }
        val remote = FakeRemote(
            jobResponse = MascotJobResponse("job-new", "READY_FOR_GENERATION"),
            recoveryFailure = MascotApiException(ApiError("JOB_NOT_FOUND", ""), 404),
        )

        val job = MascotRepository(remote, pending).create(byteArrayOf(1), "image/png")

        assertEquals("job-new", job.jobId)
        assertEquals("job-new", pending.jobId.value)
        assertEquals(null, pending.requestId.value)
        assertEquals(1, remote.createCalls)
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

    @Test fun `completed remote state starts local installation`() {
        assertEquals(
            MascotCreationState.InstallingMascot("job-1"),
            MascotJobResponse("job-1", "COMPLETED").toCreationState(),
        )
    }

    @Test fun `ready generation state is presented as paused instead of active tracking`() {
        val job = MascotJobResponse("job-1", "READY_FOR_GENERATION")
        assertEquals(MascotCreationState.GenerationPaused(job), job.toCreationState())
    }

    @Test fun `consistency state explains that pose preparation is pending`() {
        val job = MascotJobResponse("job-1", "CONSISTENCY_TEST", masterId = "master_3")
        assertEquals(MascotCreationState.PosePreparationPending(job), job.toCreationState())
    }

    @Test fun `starting a paused Master uses a stable idempotency key`() = runTest {
        val remote = FakeRemote(jobResponse = MascotJobResponse("job-1", "VALIDATING_INPUT"))
        val repository = MascotRepository(remote, FakePending("job-1"))
        repository.startMasterGeneration("job-1")
        repository.startMasterGeneration("job-1")
        assertEquals(listOf("generate-master:job-1", "generate-master:job-1"), remote.generationKeys)
    }

    @Test fun `completed package is verified promoted selected and clears pending`() = runTest {
        val root = Files.createTempDirectory("gru-install-test").toFile()
        try {
            val bytes = "valid-pose".encodeToByteArray()
            val pending = FakePending("job-1")
            val remote = FakeRemote(resultResponse = resultFixture(bytes), downloadBytes = bytes)

            assertTrue(MascotRepository(remote, pending, CustomMascotStore(root)).installCompletedMascot("job-1"))

            assertEquals("set-1" to "master_1", pending.selectedMascot)
            assertEquals(null, pending.jobId.value)
            assertEquals(1, remote.resultCalls)
            assertEquals(0, remote.createCalls)
            assertTrue(CustomMascotStore(root).poseFile("set-1", MascotRuntimeState.IDLE)?.isFile == true)
        } finally { root.deleteRecursively() }
    }

    @Test fun `corrupt completed package keeps pending job and current selection`() = runTest {
        val root = Files.createTempDirectory("gru-install-test").toFile()
        try {
            val expected = "valid-pose".encodeToByteArray()
            val pending = FakePending("job-1")
            val remote = FakeRemote(resultResponse = resultFixture(expected), downloadBytes = "corrupt".encodeToByteArray())

            assertFalse(MascotRepository(remote, pending, CustomMascotStore(root)).installCompletedMascot("job-1"))

            assertEquals("job-1", pending.jobId.value)
            assertEquals(null, pending.selectedMascot)
            assertEquals(0, remote.createCalls)
        } finally { root.deleteRecursively() }
    }

    @Test fun `installation retry downloads result again without creating a new job`() = runTest {
        val root = Files.createTempDirectory("gru-install-test").toFile()
        try {
            val valid = "valid-pose".encodeToByteArray()
            val remote = FakeRemote(resultResponse = resultFixture(valid), downloadBytes = "corrupt".encodeToByteArray())
            val repository = MascotRepository(remote, FakePending("job-1"), CustomMascotStore(root))
            assertFalse(repository.installCompletedMascot("job-1"))
            remote.downloadBytes = valid

            assertTrue(repository.installCompletedMascot("job-1"))
            assertEquals(2, remote.resultCalls)
            assertEquals(0, remote.createCalls)
        } finally { root.deleteRecursively() }
    }
}

private class FakePending(initialJobId: String? = null) : MascotPendingState {
    var selectedMascot: Pair<String, String>? = null
    override val jobId = MutableStateFlow(initialJobId)
    override val requestId = MutableStateFlow<String?>(null)
    override val cancelPending = MutableStateFlow(false)
    override fun setJobId(value: String?) { jobId.value = value }
    override fun setRequestId(value: String?) { requestId.value = value }
    override fun setCancelPending(value: Boolean) { cancelPending.value = value }
    override fun selectCustomMascot(poseSetId: String, masterId: String) { selectedMascot = poseSetId to masterId }
}

private class FakeRemote(
    var jobResponse: MascotJobResponse = MascotJobResponse("job-default", "READY_FOR_GENERATION"),
    var jobFailure: Throwable? = null,
    var recoveryFailure: Throwable? = null,
    var resultResponse: MascotResultResponse? = null,
    var downloadBytes: ByteArray? = null,
) : MascotRemoteApi {
    var createCalls = 0
    var resultCalls = 0
    val approvalKeys = mutableListOf<String>()
    val generationKeys = mutableListOf<String>()
    val cancelKeys = mutableListOf<String>()
    val recoveryKeys = mutableListOf<String>()

    override suspend fun createJob(image: ByteArray, mimeType: String, key: String): MascotJobResponse {
        createCalls += 1
        return jobResponse
    }
    override suspend fun job(jobId: String): MascotJobResponse = jobFailure?.let { throw it } ?: jobResponse
    override suspend fun recoverJob(idempotencyKey: String): MascotJobResponse {
        recoveryKeys += idempotencyKey
        return recoveryFailure?.let { throw it } ?: jobFailure?.let { throw it } ?: jobResponse
    }
    override suspend fun startMasterGeneration(jobId: String, key: String): MascotJobResponse {
        generationKeys += key
        return jobResponse
    }
    override suspend fun approveMaster(jobId: String, masterId: String, key: String): MascotJobResponse {
        approvalKeys += key
        return jobResponse
    }
    override suspend fun cancel(jobId: String, key: String): MascotJobResponse {
        cancelKeys += key
        return jobResponse
    }
    override suspend fun result(jobId: String): MascotResultResponse {
        resultCalls += 1
        return requireNotNull(resultResponse)
    }
    override suspend fun download(path: String): ByteArray = requireNotNull(downloadBytes)
}

private fun resultFixture(bytes: ByteArray): MascotResultResponse {
    val checksum = MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }
    val poses = (1..3).map { index ->
        val id = "pose_%02d".format(index)
        MascotPose(id, "Pose $index", "$id.png", checksum, "/v1/mascot/jobs/job-1/poses/$id")
    }
    return MascotResultResponse("set-1", "master_1", "v1", "model", poses)
}

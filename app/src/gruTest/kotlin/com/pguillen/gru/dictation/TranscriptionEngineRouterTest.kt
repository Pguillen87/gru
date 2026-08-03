/*
 * Copyright (C) 2026 Gru Contributors
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 */

package com.pguillen.gru.dictation

import java.io.File
import kotlinx.coroutines.test.runTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse

class TranscriptionEngineRouterTest {
    @Test
    fun `private session never calls Groq even if selection changes`() = runTest {
        var selected = TranscriptionEngine.PRIVATE_LOCAL
        var groqCreated = false
        var groqCalled = false
        val router = TranscriptionEngineRouter(
            selectedEngine = { selected },
            groqGateway = {
                groqCreated = true
                GruTranscriptionGateway { groqCalled = true; "online" }
            },
            localGateway = { GruTranscriptionGateway { "local" } },
        )

        val sessionGateway = router.create()
        selected = TranscriptionEngine.ONLINE_GROQ
        val result = sessionGateway.transcribe(File("unused.wav"))

        assertEquals("local", result)
        assertFalse(groqCreated)
        assertFalse(groqCalled)
    }

    @Test
    fun `online selection resolves only Groq`() = runTest {
        var localCalled = false
        val router = TranscriptionEngineRouter(
            selectedEngine = { TranscriptionEngine.ONLINE_GROQ },
            groqGateway = { GruTranscriptionGateway { "online" } },
            localGateway = {
                GruTranscriptionGateway { localCalled = true; "local" }
            },
        )

        assertEquals("online", router.create().transcribe(File("unused.wav")))
        assertFalse(localCalled)
    }
}

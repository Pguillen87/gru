/*
 * Copyright (C) 2026 Gru Contributors
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 */

package com.pguillen.gru.dictation

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNull
import kotlin.test.assertTrue

class TranscriptionSelectionPolicyTest {
    @Test
    fun `online requires only Groq key`() {
        assertFalse(TranscriptionSelectionPolicy.canActivate(TranscriptionEngine.ONLINE_GROQ, false, true))
        assertTrue(TranscriptionSelectionPolicy.canActivate(TranscriptionEngine.ONLINE_GROQ, true, false))
    }

    @Test
    fun `private requires only verified local model`() {
        assertFalse(TranscriptionSelectionPolicy.canActivate(TranscriptionEngine.PRIVATE_LOCAL, true, false))
        assertTrue(TranscriptionSelectionPolicy.canActivate(TranscriptionEngine.PRIVATE_LOCAL, false, true))
    }

    @Test
    fun `requesting private never retains online as active`() {
        assertNull(
            TranscriptionSelectionPolicy.engineAfterSelection(
                current = TranscriptionEngine.ONLINE_GROQ,
                requested = TranscriptionEngine.PRIVATE_LOCAL,
                targetReady = false,
            ),
        )
    }

    @Test
    fun `ready target activates atomically`() {
        assertEquals(
            TranscriptionEngine.ONLINE_GROQ,
            TranscriptionSelectionPolicy.engineAfterSelection(
                current = TranscriptionEngine.PRIVATE_LOCAL,
                requested = TranscriptionEngine.ONLINE_GROQ,
                targetReady = true,
            ),
        )
    }

    @Test
    fun `private remains active while online waits for key`() {
        assertEquals(
            TranscriptionEngine.PRIVATE_LOCAL,
            TranscriptionSelectionPolicy.engineAfterSelection(
                current = TranscriptionEngine.PRIVATE_LOCAL,
                requested = TranscriptionEngine.ONLINE_GROQ,
                targetReady = false,
            ),
        )
    }

    @Test
    fun `online without key is not retained`() {
        assertNull(
            TranscriptionSelectionPolicy.engineAfterSelection(
                current = TranscriptionEngine.ONLINE_GROQ,
                requested = TranscriptionEngine.ONLINE_GROQ,
                targetReady = false,
            ),
        )
    }

    @Test
    fun `corrupted pending online state recovers verified private engine`() {
        assertEquals(
            TranscriptionEngine.PRIVATE_LOCAL,
            TranscriptionSelectionPolicy.recoverPendingSelection(
                current = null,
                requested = TranscriptionEngine.ONLINE_GROQ,
                hasGroqKey = false,
                hasLocalModel = true,
                allowLegacyPrivateRecovery = true,
            ),
        )
    }

    @Test
    fun `online without key does not silently fall back after migration`() {
        assertNull(
            TranscriptionSelectionPolicy.recoverPendingSelection(
                current = null,
                requested = TranscriptionEngine.ONLINE_GROQ,
                hasGroqKey = false,
                hasLocalModel = true,
            ),
        )
    }

    @Test
    fun `pending private activates automatically when model becomes ready`() {
        assertEquals(
            TranscriptionEngine.PRIVATE_LOCAL,
            TranscriptionSelectionPolicy.recoverPendingSelection(
                current = null,
                requested = TranscriptionEngine.PRIVATE_LOCAL,
                hasGroqKey = true,
                hasLocalModel = true,
            ),
        )
    }

    @Test
    fun `pending private never recovers online while model is missing`() {
        assertNull(
            TranscriptionSelectionPolicy.recoverPendingSelection(
                current = TranscriptionEngine.ONLINE_GROQ,
                requested = TranscriptionEngine.PRIVATE_LOCAL,
                hasGroqKey = true,
                hasLocalModel = false,
            ),
        )
    }
}

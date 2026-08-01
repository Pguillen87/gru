/*
 * Copyright (C) 2026 Gru Contributors
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 */

package com.pguillen.gru.dictation

import kotlin.test.Test
import kotlin.test.assertFalse
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
}

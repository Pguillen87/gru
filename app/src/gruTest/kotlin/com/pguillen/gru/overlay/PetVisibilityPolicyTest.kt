package com.pguillen.gru.overlay

import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test

class PetVisibilityPolicyTest {
    @Test
    fun `shows only with enabled ready engine focused editor and visible keyboard`() {
        assertTrue(PetVisibilityPolicy.shouldShow(true, true, true, true))
        assertFalse(PetVisibilityPolicy.shouldShow(true, true, false, true))
        assertFalse(PetVisibilityPolicy.shouldShow(true, true, true, false))
    }

    @Test
    fun `stays hidden when disabled`() {
        assertFalse(PetVisibilityPolicy.shouldShow(false, true, true, true))
    }

    @Test
    fun `pauses while the requested engine is not ready`() {
        assertFalse(PetVisibilityPolicy.shouldShow(true, false, true, true))
    }

    @Test
    fun `conversation suppression hides only the pet without disabling Gru`() {
        assertFalse(PetVisibilityPolicy.shouldShow(true, true, true, true, conversationSuppressed = true))
        assertTrue(PetVisibilityPolicy.shouldShow(true, true, true, true, conversationSuppressed = false))
    }
}

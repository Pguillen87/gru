package com.pguillen.gru.overlay

import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test

class PetVisibilityPolicyTest {
    @Test
    fun `shows only with enabled focused editor and visible keyboard`() {
        assertTrue(PetVisibilityPolicy.shouldShow(true, true, true))
        assertFalse(PetVisibilityPolicy.shouldShow(true, false, true))
        assertFalse(PetVisibilityPolicy.shouldShow(true, true, false))
    }

    @Test
    fun `stays hidden when disabled`() {
        assertFalse(PetVisibilityPolicy.shouldShow(false, true, true))
    }
}

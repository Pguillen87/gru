package com.pguillen.gru.overlay

import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test

class BubbleVisibilityPolicyTest {
    @Test
    fun `shows only with enabled focused editor and visible keyboard`() {
        assertTrue(BubbleVisibilityPolicy.shouldShow(true, true, true))
        assertFalse(BubbleVisibilityPolicy.shouldShow(true, false, true))
        assertFalse(BubbleVisibilityPolicy.shouldShow(true, true, false))
    }

    @Test
    fun `stays hidden when disabled`() {
        assertFalse(BubbleVisibilityPolicy.shouldShow(false, true, true))
    }
}

package dev.patrickgold.florisboard.dictate.overlay

import org.junit.jupiter.api.Assertions.assertFalse
import org.junit.jupiter.api.Assertions.assertTrue
import org.junit.jupiter.api.Test

class BubbleVisibilityPolicyTest {
    @Test
    fun `shows only with enabled focused editor and visible keyboard`() {
        assertTrue(BubbleVisibilityPolicy.shouldShow(true, true, true, false, false))
        assertFalse(BubbleVisibilityPolicy.shouldShow(true, false, true, false, false))
        assertFalse(BubbleVisibilityPolicy.shouldShow(true, true, false, false, false))
    }

    @Test
    fun `stays hidden for blocked keyboard or recognition overlay`() {
        assertFalse(BubbleVisibilityPolicy.shouldShow(true, true, true, true, false))
        assertFalse(BubbleVisibilityPolicy.shouldShow(true, true, true, false, true))
    }
}

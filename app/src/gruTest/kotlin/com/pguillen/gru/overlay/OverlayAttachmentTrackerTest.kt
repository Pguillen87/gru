package com.pguillen.gru.overlay

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class OverlayAttachmentTrackerTest {
    @Test
    fun `moves through attach visible and detach`() {
        val tracker = OverlayAttachmentTracker()

        tracker.beginAttach()
        assertEquals(OverlayAttachmentState.Attaching, tracker.state)
        tracker.markVisible()
        assertEquals(OverlayAttachmentState.Visible, tracker.state)
        tracker.detach()
        assertEquals(OverlayAttachmentState.Detached, tracker.state)
    }

    @Test
    fun `limits automatic recovery attempts`() {
        val tracker = OverlayAttachmentTracker(maxRecoveryAttempts = 2)

        tracker.markFailed()
        assertTrue(tracker.reserveRecovery())
        assertTrue(tracker.reserveRecovery())
        assertFalse(tracker.reserveRecovery())
        assertEquals(2, tracker.recoveryAttempts)
    }

    @Test
    fun `visible frame resets recovery budget`() {
        val tracker = OverlayAttachmentTracker(maxRecoveryAttempts = 1)

        assertTrue(tracker.reserveRecovery())
        tracker.markVisible()

        assertEquals(0, tracker.recoveryAttempts)
        assertTrue(tracker.reserveRecovery())
    }
}

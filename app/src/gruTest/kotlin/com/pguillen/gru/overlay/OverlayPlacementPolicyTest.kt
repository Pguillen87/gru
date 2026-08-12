package com.pguillen.gru.overlay

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class OverlayPlacementPolicyTest {
    private val size = OverlaySize(120, 120)
    private val usable = OverlayRect(0, 24, 1080, 2200)

    @Test fun `initial position stays above ime and away from editor`() {
        val environment = OverlayEnvironment(
            usable,
            listOf(
                AvoidanceRegion(OverlayRect(0, 1500, 1080, 2200), AvoidanceKind.IME),
                AvoidanceRegion(OverlayRect(40, 1340, 1040, 1500), AvoidanceKind.EDITOR),
            ),
        )
        val point = OverlayPlacementPolicy.initialPosition(environment, size, 12)
        assertTrue(OverlayPlacementPolicy.isSafe(point, environment, size, 12))
        assertTrue(point.y + size.height < 1340)
    }

    @Test fun `saved unsafe position moves to nearest safe area`() {
        val editor = OverlayRect(700, 900, 1080, 1100)
        val environment = OverlayEnvironment(usable, listOf(AvoidanceRegion(editor, AvoidanceKind.EDITOR)))
        val point = OverlayPlacementPolicy.resolve(OverlayPoint(900, 940), environment, size, 12)
        assertTrue(OverlayPlacementPolicy.isSafe(point, environment, size, 12))
        assertFalse(OverlayRect(point.x, point.y, point.x + 120, point.y + 120).intersects(editor.expanded(12)))
    }

    @Test fun `safe manual position is preserved`() {
        val environment = OverlayEnvironment(usable, emptyList())
        val preferred = OverlayPoint(80, 300)
        assertEquals(preferred, OverlayPlacementPolicy.resolve(preferred, environment, size, 12))
    }

    @Test fun `drag bounds never enter the ime`() {
        val environment = OverlayEnvironment(
            usable,
            listOf(AvoidanceRegion(OverlayRect(0, 1400, 1080, 2200), AvoidanceKind.IME)),
        )
        assertEquals(1268, OverlayPlacementPolicy.dragBounds(environment, size, 12).bottom)
    }
}

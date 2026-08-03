package com.pguillen.gru.overlay

import kotlin.test.Test
import kotlin.test.assertEquals

class LivingPetViewGeometryTest {
    @Test fun `portrait custom mascot keeps its aspect ratio inside square overlay`() {
        val bounds = aspectFitBottomBounds(400, 800, 200, 200)

        assertEquals(50f, bounds.left)
        assertEquals(0f, bounds.top)
        assertEquals(150f, bounds.right)
        assertEquals(200f, bounds.bottom)
    }

    @Test fun `landscape custom mascot is centered and bottom aligned`() {
        val bounds = aspectFitBottomBounds(800, 400, 200, 200)

        assertEquals(0f, bounds.left)
        assertEquals(100f, bounds.top)
        assertEquals(200f, bounds.right)
        assertEquals(200f, bounds.bottom)
    }
}

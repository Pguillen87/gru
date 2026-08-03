package com.pguillen.gru.mascot

import kotlin.test.Test
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class MascotIntegrityTest {
    @Test fun `downloaded bytes must match manifest checksum`() {
        val bytes = "approved-pose".encodeToByteArray()
        assertTrue(bytes.matchesSha256("ef5c48f8c32844a780846d0aacc1c191c467520aedee449da9a50e8ac1debf74"))
        assertFalse("corrupted".encodeToByteArray().matchesSha256("ef5c48f8c32844a780846d0aacc1c191c467520aedee449da9a50e8ac1debf74"))
    }
}

package com.pguillen.gru

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse

class GruNavigationTest {
    @Test
    fun exposesTheFiveApprovedDestinationsInOrder() {
        assertEquals(
            listOf(
                GruDestination.PERMISSIONS,
                GruDestination.VOICE,
                GruDestination.CONTROL,
                GruDestination.MASCOTS,
                GruDestination.CREATE_MASCOT,
            ),
            GruDestination.entries,
        )
        assertFalse(GruDestination.entries.any { it.name == "CONTACTS" })
    }

    @Test
    fun centralDestinationIsNavigationOnly() {
        assertEquals(2, GruDestination.CONTROL.ordinal)
        assertEquals(R.string.gru__nav_control, GruDestination.CONTROL.label)
    }
}

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
                GruDestination.PERCH,
            ),
            GruDestination.entries,
        )
        assertFalse(GruDestination.entries.any { it.name == "CONTACTS" })
        assertEquals(R.string.gru__nav_perch, GruDestination.PERCH.label)
    }

    @Test
    fun centralDestinationIsNavigationOnly() {
        assertEquals(2, GruDestination.CONTROL.ordinal)
        assertEquals(R.string.gru__nav_control, GruDestination.CONTROL.label)
    }

    @Test
    fun mainNavigationRemainsAfterOnboardingWhileEngineIsPreparing() {
        assertEquals(true, shouldShowMainNavigation(onboardingCompleted = true))
        assertEquals(false, shouldShowMainNavigation(onboardingCompleted = false))
    }
}

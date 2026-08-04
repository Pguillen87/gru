/*
 * Copyright (C) 2026 Gru Contributors
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 */

package com.pguillen.gru

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class GruPetSizeTest {
    @Test
    fun `sizes keep a stable hierarchy around the medium baseline`() {
        assertTrue(GruPetSize.SMALL.scale < GruPetSize.MEDIUM.scale)
        assertTrue(GruPetSize.MEDIUM.scale < GruPetSize.LARGE.scale)
        assertEquals(1f, GruPetSize.MEDIUM.scale)
    }
}

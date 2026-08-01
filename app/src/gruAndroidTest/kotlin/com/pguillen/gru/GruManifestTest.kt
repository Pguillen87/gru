/*
 * Copyright (C) 2026 Gru Contributors
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 */

package com.pguillen.gru

import android.Manifest
import android.content.pm.PackageManager
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.pguillen.gru.overlay.GruAccessibilityService
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class GruManifestTest {
    @Test
    fun exposesAccessibilityServiceWithoutImeService() {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val services = context.packageManager
            .getPackageInfo(context.packageName, PackageManager.GET_SERVICES)
            .services
            .orEmpty()

        assertTrue(context.packageName.startsWith("com.pguillen.gru"))
        assertTrue(services.any { it.name == GruAccessibilityService::class.java.name })
        assertFalse(services.any { it.permission == Manifest.permission.BIND_INPUT_METHOD })
    }
}

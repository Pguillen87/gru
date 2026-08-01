/*
 * Copyright (C) 2026 Gru Contributors
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 */

package com.pguillen.gru

import android.content.Context
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import com.pguillen.gru.security.GroqApiKeyStore
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith

@RunWith(AndroidJUnit4::class)
class GroqApiKeyStoreInstrumentedTest {
    @Test
    fun encryptsApiKeyWithAndroidKeystore() {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val keyStore = GroqApiKeyStore(context)
        val secret = "gsk_instrumented_test_only"
        keyStore.clear()

        assertTrue(keyStore.write(secret))
        assertEquals(secret, keyStore.read())
        assertFalse(preferencesXml(context, "gru_secrets").contains(secret))

        assertTrue(keyStore.clear())
        assertEquals("", keyStore.read())
    }

    @Test
    fun migratesAndRemovesLegacyPlaintextAfterVerification() {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val legacyStore = context.getSharedPreferences("gru_preferences", Context.MODE_PRIVATE)
        val secret = "gsk_legacy_migration_test"
        GroqApiKeyStore(context).clear()
        legacyStore.edit().putString("groq_api_key", secret).commit()

        val preferences = GruPreferences.get(context)

        assertEquals(secret, preferences.groqApiKey)
        assertFalse(legacyStore.contains("groq_api_key"))
        assertFalse(preferencesXml(context, "gru_secrets").contains(secret))
        preferences.removeGroqApiKey()
    }

    private fun preferencesXml(context: Context, name: String): String {
        val file = context.dataDir.resolve("shared_prefs/$name.xml")
        return if (file.exists()) file.readText() else ""
    }
}

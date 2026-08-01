/*
 * Copyright (C) 2026 Gru Contributors
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 */

package com.pguillen.gru.security

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

class GroqApiKeyStore(context: Context) {
    private val appContext = context.applicationContext
    private val store = appContext.getSharedPreferences(SECRET_STORE, Context.MODE_PRIVATE)

    fun read(): String = runCatching {
        val payload = store.getString(ENCRYPTED_KEY, null) ?: return ""
        val decoded = Base64.decode(payload, Base64.NO_WRAP)
        require(decoded.size > IV_BYTES)
        val cipher = Cipher.getInstance(TRANSFORMATION)
        cipher.init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(GCM_TAG_BITS, decoded, 0, IV_BYTES))
        cipher.updateAAD(aad())
        cipher.doFinal(decoded, IV_BYTES, decoded.size - IV_BYTES).decodeToString()
    }.getOrDefault("")

    fun write(value: String): Boolean {
        val normalized = value.trim()
        if (normalized.isEmpty()) return clear()
        return runCatching {
            val cipher = Cipher.getInstance(TRANSFORMATION)
            cipher.init(Cipher.ENCRYPT_MODE, key())
            cipher.updateAAD(aad())
            val encrypted = cipher.iv + cipher.doFinal(normalized.encodeToByteArray())
            store.edit()
                .putString(ENCRYPTED_KEY, Base64.encodeToString(encrypted, Base64.NO_WRAP))
                .commit() && read() == normalized
        }.getOrDefault(false)
    }

    fun clear(): Boolean = store.edit().remove(ENCRYPTED_KEY).commit()

    private fun key(): SecretKey {
        val keyStore = KeyStore.getInstance(KEYSTORE).apply { load(null) }
        (keyStore.getKey(KEY_ALIAS, null) as? SecretKey)?.let { return it }
        return KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, KEYSTORE).run {
            init(
                KeyGenParameterSpec.Builder(
                    KEY_ALIAS,
                    KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT,
                )
                    .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                    .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                    .setKeySize(256)
                    .build(),
            )
            generateKey()
        }
    }

    private fun aad(): ByteArray = "${appContext.packageName}:groq".encodeToByteArray()

    private companion object {
        const val KEYSTORE = "AndroidKeyStore"
        const val KEY_ALIAS = "gru_groq_api_key_v1"
        const val SECRET_STORE = "gru_secrets"
        const val ENCRYPTED_KEY = "groq_api_key_ciphertext"
        const val TRANSFORMATION = "AES/GCM/NoPadding"
        const val IV_BYTES = 12
        const val GCM_TAG_BITS = 128
    }
}

/*
 * Copyright (C) 2026 Gru Contributors
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 */

package com.pguillen.gru

import android.content.Context
import android.content.SharedPreferences
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

class GruPreferences private constructor(context: Context) {
    private val store = context.getSharedPreferences(FILE_NAME, Context.MODE_PRIVATE)

    private val mutableEnabled = MutableStateFlow(store.getBoolean(KEY_ENABLED, false))
    val enabled: StateFlow<Boolean> = mutableEnabled.asStateFlow()

    private val mutablePet = MutableStateFlow(store.enumValue(KEY_PET, GruPet.FAISCA))
    val pet: StateFlow<GruPet> = mutablePet.asStateFlow()

    private val mutableSize = MutableStateFlow(store.enumValue(KEY_SIZE, GruPetSize.MEDIUM))
    val size: StateFlow<GruPetSize> = mutableSize.asStateFlow()

    private val mutableOpacity = MutableStateFlow(store.getInt(KEY_OPACITY, 100).coerceIn(40, 100))
    val opacity: StateFlow<Int> = mutableOpacity.asStateFlow()

    var groqApiKey: String
        get() = store.getString(KEY_GROQ_API_KEY, "").orEmpty()
        set(value) = store.edit().putString(KEY_GROQ_API_KEY, value.trim()).apply()

    var groqModel: String
        get() = store.getString(KEY_GROQ_MODEL, DEFAULT_GROQ_MODEL).orEmpty().ifBlank { DEFAULT_GROQ_MODEL }
        set(value) = store.edit().putString(KEY_GROQ_MODEL, value.trim().ifBlank { DEFAULT_GROQ_MODEL }).apply()

    fun setEnabled(value: Boolean) {
        mutableEnabled.value = value
        store.edit().putBoolean(KEY_ENABLED, value).apply()
    }

    fun setPet(value: GruPet) {
        mutablePet.value = value
        store.edit().putString(KEY_PET, value.name).apply()
    }

    fun setSize(value: GruPetSize) {
        mutableSize.value = value
        store.edit().putString(KEY_SIZE, value.name).apply()
    }

    fun setOpacity(value: Int) {
        val normalized = value.coerceIn(40, 100)
        mutableOpacity.value = normalized
        store.edit().putInt(KEY_OPACITY, normalized).apply()
    }

    private inline fun <reified T : Enum<T>> SharedPreferences.enumValue(key: String, fallback: T): T =
        getString(key, null)?.let { stored -> enumValues<T>().firstOrNull { it.name == stored } } ?: fallback

    companion object {
        const val DEFAULT_GROQ_MODEL = "whisper-large-v3-turbo"

        private const val FILE_NAME = "gru_preferences"
        private const val KEY_ENABLED = "pet_enabled"
        private const val KEY_PET = "pet"
        private const val KEY_SIZE = "pet_size"
        private const val KEY_OPACITY = "pet_opacity"
        private const val KEY_GROQ_API_KEY = "groq_api_key"
        private const val KEY_GROQ_MODEL = "groq_model"

        @Volatile private var instance: GruPreferences? = null

        fun get(context: Context): GruPreferences = instance ?: synchronized(this) {
            instance ?: GruPreferences(context.applicationContext).also { instance = it }
        }
    }
}

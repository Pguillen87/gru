/*
 * Copyright (C) 2026 Gru Contributors
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 */

package com.pguillen.gru

import android.content.Context
import android.content.SharedPreferences
import android.util.Log
import com.pguillen.gru.dictation.TranscriptionEngine
import com.pguillen.gru.dictation.TranscriptionSelectionPolicy
import com.pguillen.gru.security.GroqApiKeyStore
import com.pguillen.gru.mascot.MascotSource
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

class GruPreferences private constructor(context: Context) {
    private val store = context.getSharedPreferences(FILE_NAME, Context.MODE_PRIVATE)
    private val apiKeyStore = GroqApiKeyStore(context)

    private val mutableEnabled = MutableStateFlow(store.getBoolean(KEY_ENABLED, false))
    val enabled: StateFlow<Boolean> = mutableEnabled.asStateFlow()

    private val mutablePet = MutableStateFlow(store.enumValue(KEY_PET, GruPet.FAISCA))
    val pet: StateFlow<GruPet> = mutablePet.asStateFlow()

    private val mutableMascotSource = MutableStateFlow(readMascotSource())
    val mascotSource: StateFlow<MascotSource> = mutableMascotSource.asStateFlow()

    private val mutablePendingMascotJobId = MutableStateFlow(store.getString(KEY_PENDING_MASCOT_JOB, null))
    val pendingMascotJobId: StateFlow<String?> = mutablePendingMascotJobId.asStateFlow()

    private val mutablePendingMascotRequestId = MutableStateFlow(store.getString(KEY_PENDING_MASCOT_REQUEST, null))
    val pendingMascotRequestId: StateFlow<String?> = mutablePendingMascotRequestId.asStateFlow()

    private val mutableMascotCancelPending = MutableStateFlow(store.getBoolean(KEY_MASCOT_CANCEL_PENDING, false))
    val mascotCancelPending: StateFlow<Boolean> = mutableMascotCancelPending.asStateFlow()

    private val mutableSize = MutableStateFlow(store.enumValue(KEY_SIZE, GruPetSize.MEDIUM))
    val size: StateFlow<GruPetSize> = mutableSize.asStateFlow()

    private val mutableOpacity = MutableStateFlow(store.getInt(KEY_OPACITY, 100).coerceIn(40, 100))
    val opacity: StateFlow<Int> = mutableOpacity.asStateFlow()

    private val storedEngine = store.nullableEnumValue<TranscriptionEngine>(KEY_ENGINE)
    private val storedRequestedEngine =
        store.nullableEnumValue<TranscriptionEngine>(KEY_REQUESTED_ENGINE) ?: storedEngine
    private val initialEngine = storedEngine

    private val mutableEngine = MutableStateFlow(initialEngine)
    val engine: StateFlow<TranscriptionEngine?> = mutableEngine.asStateFlow()

    private val mutableRequestedEngine = MutableStateFlow(storedRequestedEngine)
    val requestedEngine: StateFlow<TranscriptionEngine?> = mutableRequestedEngine.asStateFlow()
    private var legacySelectionRecoveryPending = !store.getBoolean(KEY_TRANSACTIONAL_SELECTION_MIGRATED, false)

    private val mutableGroqApiKey = MutableStateFlow(migrateLegacyApiKey())
    val groqApiKeyState: StateFlow<String> = mutableGroqApiKey.asStateFlow()

    init {
        if (storedEngine != initialEngine) {
            store.edit().remove(KEY_ENGINE).apply()
        }
    }

    var groqApiKey: String
        get() = mutableGroqApiKey.value
        set(value) {
            val normalized = value.trim()
            if (apiKeyStore.write(normalized)) mutableGroqApiKey.value = normalized
        }

    var groqModel: String
        get() = store.getString(KEY_GROQ_MODEL, DEFAULT_GROQ_MODEL).orEmpty().ifBlank { DEFAULT_GROQ_MODEL }
        set(value) = store.edit().putString(KEY_GROQ_MODEL, value.trim().ifBlank { DEFAULT_GROQ_MODEL }).apply()

    fun setEnabled(value: Boolean) {
        mutableEnabled.value = value
        store.edit().putBoolean(KEY_ENABLED, value).apply()
    }

    fun setPet(value: GruPet) {
        mutablePet.value = value
        mutableMascotSource.value = MascotSource.BuiltIn(value)
        store.edit().putString(KEY_PET, value.name).apply()
        store.edit().putString(KEY_MASCOT_SOURCE, SOURCE_BUILT_IN).remove(KEY_CUSTOM_POSE_SET).remove(KEY_CUSTOM_MASTER).apply()
    }

    fun selectCustomMascot(poseSetId: String, masterId: String) {
        mutableMascotSource.value = MascotSource.Custom(poseSetId, masterId)
        store.edit().putString(KEY_MASCOT_SOURCE, SOURCE_CUSTOM)
            .putString(KEY_CUSTOM_POSE_SET, poseSetId).putString(KEY_CUSTOM_MASTER, masterId).apply()
    }

    fun setPendingMascotJobId(jobId: String?) {
        mutablePendingMascotJobId.value = jobId
        store.edit().apply { if (jobId == null) remove(KEY_PENDING_MASCOT_JOB) else putString(KEY_PENDING_MASCOT_JOB, jobId) }.apply()
    }

    fun setPendingMascotRequestId(requestId: String?) {
        mutablePendingMascotRequestId.value = requestId
        store.edit().apply { if (requestId == null) remove(KEY_PENDING_MASCOT_REQUEST) else putString(KEY_PENDING_MASCOT_REQUEST, requestId) }.apply()
    }

    fun setMascotCancelPending(value: Boolean) {
        mutableMascotCancelPending.value = value
        store.edit().putBoolean(KEY_MASCOT_CANCEL_PENDING, value).apply()
    }

    private fun readMascotSource(): MascotSource {
        if (store.getString(KEY_MASCOT_SOURCE, SOURCE_BUILT_IN) != SOURCE_CUSTOM) return MascotSource.BuiltIn(mutablePet.value)
        val poseSetId = store.getString(KEY_CUSTOM_POSE_SET, null)
        val masterId = store.getString(KEY_CUSTOM_MASTER, null)
        return if (poseSetId.isNullOrBlank() || masterId.isNullOrBlank()) MascotSource.BuiltIn(mutablePet.value)
        else MascotSource.Custom(poseSetId, masterId)
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

    fun selectEngine(value: TranscriptionEngine, hasLocalModel: Boolean): Boolean {
        val previous = mutableEngine.value
        val targetReady = TranscriptionSelectionPolicy.canActivate(
            engine = value,
            hasGroqKey = mutableGroqApiKey.value.isNotBlank(),
            hasLocalModel = hasLocalModel,
        )
        val active = TranscriptionSelectionPolicy.engineAfterSelection(previous, value, targetReady)
        if (!persistSelection(requested = value, active = active)) return false
        logSelection("requested", previous, value, active, targetReady)
        return active == value
    }

    fun reconcileEngine(hasLocalModel: Boolean): Boolean {
        val previous = mutableEngine.value
        val requested = mutableRequestedEngine.value
        val active = TranscriptionSelectionPolicy.recoverPendingSelection(
            current = previous,
            requested = requested,
            hasGroqKey = mutableGroqApiKey.value.isNotBlank(),
            hasLocalModel = hasLocalModel,
            allowLegacyPrivateRecovery = legacySelectionRecoveryPending,
        )
        if (active != previous) {
            if (!persistSelection(requested = requested, active = active)) return false
            logSelection("reconciled", previous, requested, active, active == requested)
        }
        if (legacySelectionRecoveryPending) {
            legacySelectionRecoveryPending = false
            store.edit().putBoolean(KEY_TRANSACTIONAL_SELECTION_MIGRATED, true).apply()
        }
        return active != null && active == requested
    }

    fun clearActiveEngine(reason: String) {
        val previous = mutableEngine.value
        if (persistSelection(requested = mutableRequestedEngine.value, active = null)) {
            Log.i(TAG, "event=engine_cleared previous=$previous requested=${mutableRequestedEngine.value} reason=$reason")
        }
    }

    private fun persistSelection(requested: TranscriptionEngine?, active: TranscriptionEngine?): Boolean {
        val editor = store.edit()
        if (requested == null) editor.remove(KEY_REQUESTED_ENGINE) else editor.putString(KEY_REQUESTED_ENGINE, requested.name)
        if (active == null) editor.remove(KEY_ENGINE) else editor.putString(KEY_ENGINE, active.name)
        if (!editor.commit()) {
            Log.e(TAG, "event=engine_persist_failed requested=$requested active=$active")
            return false
        }
        mutableRequestedEngine.value = requested
        mutableEngine.value = active
        return true
    }

    private fun logSelection(
        event: String,
        previous: TranscriptionEngine?,
        requested: TranscriptionEngine?,
        active: TranscriptionEngine?,
        targetReady: Boolean,
    ) {
        Log.i(
            TAG,
            "event=engine_$event previous=$previous requested=$requested active=$active targetReady=$targetReady",
        )
    }

    fun removeGroqApiKey() {
        if (apiKeyStore.clear()) mutableGroqApiKey.value = ""
    }

    private fun migrateLegacyApiKey(): String {
        val encrypted = apiKeyStore.read()
        if (encrypted.isNotBlank()) {
            store.edit().remove(KEY_GROQ_API_KEY).apply()
            return encrypted
        }
        val legacy = store.getString(KEY_GROQ_API_KEY, "").orEmpty().trim()
        if (legacy.isNotEmpty() && apiKeyStore.write(legacy) && apiKeyStore.read() == legacy) {
            store.edit().remove(KEY_GROQ_API_KEY).commit()
        }
        return apiKeyStore.read().ifBlank { legacy }
    }

    private inline fun <reified T : Enum<T>> SharedPreferences.enumValue(key: String, fallback: T): T =
        getString(key, null)?.let { stored -> enumValues<T>().firstOrNull { it.name == stored } } ?: fallback

    private inline fun <reified T : Enum<T>> SharedPreferences.nullableEnumValue(key: String): T? =
        getString(key, null)?.let { stored -> enumValues<T>().firstOrNull { it.name == stored } }

    companion object {
        const val DEFAULT_GROQ_MODEL = "whisper-large-v3-turbo"
        private const val TAG = "GruEngine"

        private const val FILE_NAME = "gru_preferences"
        private const val KEY_ENABLED = "pet_enabled"
        private const val KEY_PET = "pet"
        private const val KEY_MASCOT_SOURCE = "mascot_source"
        private const val KEY_CUSTOM_POSE_SET = "custom_pose_set"
        private const val KEY_CUSTOM_MASTER = "custom_master"
        private const val KEY_PENDING_MASCOT_JOB = "pending_mascot_job"
        private const val KEY_PENDING_MASCOT_REQUEST = "pending_mascot_request"
        private const val KEY_MASCOT_CANCEL_PENDING = "mascot_cancel_pending"
        private const val KEY_SIZE = "pet_size"
        private const val KEY_OPACITY = "pet_opacity"
        private const val KEY_GROQ_API_KEY = "groq_api_key"
        private const val KEY_GROQ_MODEL = "groq_model"
        private const val KEY_ENGINE = "transcription_engine"
        private const val KEY_REQUESTED_ENGINE = "requested_transcription_engine"
        private const val KEY_TRANSACTIONAL_SELECTION_MIGRATED = "transactional_selection_migrated"
        private const val SOURCE_BUILT_IN = "built_in"
        private const val SOURCE_CUSTOM = "custom"

        @Volatile private var instance: GruPreferences? = null

        fun get(context: Context): GruPreferences = instance ?: synchronized(this) {
            instance ?: GruPreferences(context.applicationContext).also { instance = it }
        }
    }
}

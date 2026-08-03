/*
 * Copyright (C) 2026 Gru Contributors
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 */

package com.pguillen.gru.overlay

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

internal data class GruOverlayHealthState(
    val serviceConnected: Boolean = false,
    val attachment: OverlayAttachmentState = OverlayAttachmentState.Detached,
    val hasRenderedFrame: Boolean = false,
    val recoveryAttempts: Int = 0,
)

internal object GruOverlayHealth {
    private val mutableState = MutableStateFlow(GruOverlayHealthState())
    val state: StateFlow<GruOverlayHealthState> = mutableState.asStateFlow()

    fun serviceConnected() {
        mutableState.value = GruOverlayHealthState(serviceConnected = true)
    }

    fun serviceDisconnected() {
        mutableState.value = GruOverlayHealthState()
    }

    fun overlayChanged(attachment: OverlayAttachmentState, recoveryAttempts: Int) {
        val current = mutableState.value
        mutableState.value = current.copy(
            attachment = attachment,
            hasRenderedFrame = current.hasRenderedFrame || attachment == OverlayAttachmentState.Visible,
            recoveryAttempts = recoveryAttempts,
        )
    }
}

/*
 * Copyright (C) 2026 Gru Contributors
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 */

package com.pguillen.gru.overlay

internal enum class OverlayAttachmentState {
    Detached,
    Attaching,
    Visible,
    Failed,
}

internal class OverlayAttachmentTracker(private val maxRecoveryAttempts: Int = 2) {
    var state: OverlayAttachmentState = OverlayAttachmentState.Detached
        private set

    var recoveryAttempts: Int = 0
        private set

    fun beginAttach() {
        state = OverlayAttachmentState.Attaching
    }

    fun markVisible() {
        state = OverlayAttachmentState.Visible
        recoveryAttempts = 0
    }

    fun markFailed() {
        state = OverlayAttachmentState.Failed
    }

    fun reserveRecovery(): Boolean {
        if (recoveryAttempts >= maxRecoveryAttempts) return false
        recoveryAttempts++
        return true
    }

    fun detach(resetAttempts: Boolean = true) {
        state = OverlayAttachmentState.Detached
        if (resetAttempts) recoveryAttempts = 0
    }
}

/*
 * Copyright (C) 2026 DevEmperor (Dictate)
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 */

package dev.patrickgold.florisboard.dictate.overlay

internal object BubbleVisibilityPolicy {
    fun shouldShow(
        enabled: Boolean,
        editableFocused: Boolean,
        imeVisible: Boolean,
        blockedByOwnKeyboard: Boolean,
        recognitionOverlayActive: Boolean,
    ): Boolean = enabled &&
        editableFocused &&
        imeVisible &&
        !blockedByOwnKeyboard &&
        !recognitionOverlayActive
}

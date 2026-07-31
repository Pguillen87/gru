/*
 * Copyright (C) 2026 DevEmperor (Dictate)
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 */

package com.pguillen.gru.overlay

internal object BubbleVisibilityPolicy {
    fun shouldShow(
        enabled: Boolean,
        editableFocused: Boolean,
        imeVisible: Boolean,
    ): Boolean = enabled &&
        editableFocused &&
        imeVisible
}

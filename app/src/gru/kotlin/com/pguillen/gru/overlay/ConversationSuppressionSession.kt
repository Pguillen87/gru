package com.pguillen.gru.overlay

import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

internal data class ConversationSuppressionState(
    val sessionId: Long,
    val suppressedKeys: Set<String>,
) {
    val count: Int get() = suppressedKeys.size
}

/** Process-visible, service-session-only state. Nothing is written to disk. */
internal object ConversationSuppressionSession {
    private val mutableState = MutableStateFlow(ConversationSuppressionState(0L, emptySet()))
    val state: StateFlow<ConversationSuppressionState> = mutableState.asStateFlow()

    @Synchronized
    fun startSession(sessionId: Long) {
        mutableState.value = ConversationSuppressionState(sessionId, emptySet())
    }

    @Synchronized
    fun suppress(context: ConversationContext): Boolean {
        val current = mutableState.value
        if (context.key in current.suppressedKeys) return false
        mutableState.value = current.copy(suppressedKeys = current.suppressedKeys + context.key)
        return true
    }

    fun isSuppressed(context: ConversationContext?): Boolean =
        context != null && context.key in mutableState.value.suppressedKeys

    @Synchronized
    fun clearAll(): Int {
        val current = mutableState.value
        val removed = current.count
        if (removed > 0) mutableState.value = current.copy(suppressedKeys = emptySet())
        return removed
    }
}

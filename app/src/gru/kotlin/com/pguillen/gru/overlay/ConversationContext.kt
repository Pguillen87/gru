package com.pguillen.gru.overlay

import java.security.MessageDigest
import java.security.SecureRandom

internal enum class ConversationContextConfidence { STABLE_STRUCTURAL, EPHEMERAL_WINDOW }

internal data class ConversationContext(
    val key: String,
    val confidence: ConversationContextConfidence,
)

internal data class ConversationStructure(
    val packageName: String,
    val windowId: Int,
    val windowGeneration: Long,
    val rootUniqueId: String?,
    val rootViewId: String?,
    val rootClassName: String?,
    val rootChildCount: Int,
    val editorUniqueId: String?,
    val editorViewId: String?,
    val editorClassName: String?,
    val editorBounds: OverlayRect,
)

internal interface ConversationContextResolver {
    fun startSession()
    fun resolve(structure: ConversationStructure?): ConversationContext?
}

/** Creates opaque session-scoped keys without reading or retaining any accessibility text. */
internal class StructuralConversationContextResolver(
    private val random: SecureRandom = SecureRandom(),
) : ConversationContextResolver {
    private var sessionSalt = newSalt()

    override fun startSession() {
        sessionSalt = newSalt()
    }

    override fun resolve(structure: ConversationStructure?): ConversationContext? {
        structure ?: return null
        if (structure.packageName.isBlank() || structure.windowId < 0) return null
        val hasStableNodeIdentity = !structure.rootUniqueId.isNullOrBlank() &&
            !structure.editorUniqueId.isNullOrBlank()
        val confidence = if (hasStableNodeIdentity) {
            ConversationContextConfidence.STABLE_STRUCTURAL
        } else {
            ConversationContextConfidence.EPHEMERAL_WINDOW
        }
        val material = listOf(
            structure.packageName,
            structure.windowId.toString(),
            if (confidence == ConversationContextConfidence.EPHEMERAL_WINDOW) structure.windowGeneration.toString() else "stable",
            structure.rootUniqueId.orEmpty(),
            structure.rootViewId.orEmpty(),
            structure.rootClassName.orEmpty(),
            structure.rootChildCount.toString(),
            structure.editorUniqueId.orEmpty(),
            structure.editorViewId.orEmpty(),
            structure.editorClassName.orEmpty(),
            structure.editorBounds.toString(),
        ).joinToString("\u0000").toByteArray(Charsets.UTF_8)
        val digest = MessageDigest.getInstance("SHA-256").apply {
            update(sessionSalt)
            update(material)
        }.digest().joinToString("") { "%02x".format(it) }
        return ConversationContext(digest.take(32), confidence)
    }

    private fun newSalt() = ByteArray(32).also(random::nextBytes)
}

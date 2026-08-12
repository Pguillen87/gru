package com.pguillen.gru.overlay

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNotEquals
import kotlin.test.assertNotNull
import kotlin.test.assertTrue

class ConversationSuppressionTest {
    @Test fun `stable structural identity survives repeated resolution in one session`() {
        val resolver = StructuralConversationContextResolver().also { it.startSession() }
        val first = assertNotNull(resolver.resolve(structure(rootUnique = "root-a", editorUnique = "editor-a")))
        val repeated = assertNotNull(resolver.resolve(structure(rootUnique = "root-a", editorUnique = "editor-a")))
        val another = assertNotNull(resolver.resolve(structure(rootUnique = "root-b", editorUnique = "editor-b")))
        assertEquals(ConversationContextConfidence.STABLE_STRUCTURAL, first.confidence)
        assertEquals(first.key, repeated.key)
        assertNotEquals(first.key, another.key)
    }

    @Test fun `ephemeral identity changes when active window generation changes`() {
        val resolver = StructuralConversationContextResolver().also { it.startSession() }
        val first = assertNotNull(resolver.resolve(structure(windowGeneration = 1)))
        val nextScreen = assertNotNull(resolver.resolve(structure(windowGeneration = 2)))
        assertEquals(ConversationContextConfidence.EPHEMERAL_WINDOW, first.confidence)
        assertNotEquals(first.key, nextScreen.key)
    }

    @Test fun `new service session invalidates previous opaque keys`() {
        val resolver = StructuralConversationContextResolver()
        val structure = structure(rootUnique = "root", editorUnique = "editor")
        val previous = assertNotNull(resolver.resolve(structure))
        resolver.startSession()
        assertNotEquals(previous.key, assertNotNull(resolver.resolve(structure)).key)
    }

    @Test fun `suppression is scoped to session and can be cleared`() {
        val first = ConversationContext("one", ConversationContextConfidence.STABLE_STRUCTURAL)
        val second = ConversationContext("two", ConversationContextConfidence.STABLE_STRUCTURAL)
        ConversationSuppressionSession.startSession(10L)
        assertTrue(ConversationSuppressionSession.suppress(first))
        assertTrue(ConversationSuppressionSession.isSuppressed(first))
        assertFalse(ConversationSuppressionSession.isSuppressed(second))
        assertEquals(1, ConversationSuppressionSession.clearAll())
        assertFalse(ConversationSuppressionSession.isSuppressed(first))
        ConversationSuppressionSession.suppress(first)
        ConversationSuppressionSession.startSession(11L)
        assertEquals(0, ConversationSuppressionSession.state.value.count)
    }

    @Test fun `drag suppresses only after release inside target`() {
        val machine = OverlayInteractionMachine()
        machine.beginDrag()
        assertTrue(machine.updateSuppressionTarget(true))
        assertFalse(machine.updateSuppressionTarget(true))
        assertEquals(DragReleaseAction.SUPPRESS, machine.release())
        machine.suppressionCompleted()
        assertEquals(OverlayInteractionState.SUPPRESSED, machine.state)
    }

    @Test fun `leaving target before release only snaps`() {
        val machine = OverlayInteractionMachine()
        machine.beginDrag()
        machine.updateSuppressionTarget(true)
        machine.updateSuppressionTarget(false)
        assertEquals(DragReleaseAction.SNAP_TO_EDGE, machine.release())
        assertEquals(OverlayInteractionState.VISIBLE, machine.state)
    }

    @Test fun `target uses pet center rather than edge overlap`() {
        val target = OverlayRect(100, 100, 300, 220)
        assertTrue(isOverSuppressionTarget(OverlayRect(120, 80, 240, 200), target))
        assertFalse(isOverSuppressionTarget(OverlayRect(20, 20, 110, 110), target))
    }

    private fun structure(
        windowGeneration: Long = 1L,
        rootUnique: String? = null,
        editorUnique: String? = null,
    ) = ConversationStructure(
        packageName = "example.messaging",
        windowId = 7,
        windowGeneration = windowGeneration,
        rootUniqueId = rootUnique,
        rootViewId = "root",
        rootClassName = "RootLayout",
        rootChildCount = 4,
        editorUniqueId = editorUnique,
        editorViewId = "composer",
        editorClassName = "EditText",
        editorBounds = OverlayRect(20, 1200, 1060, 1350),
    )
}

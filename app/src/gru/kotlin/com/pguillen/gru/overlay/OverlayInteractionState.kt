package com.pguillen.gru.overlay

internal enum class OverlayInteractionState {
    VISIBLE,
    DRAGGING,
    DRAGGING_OVER_SUPPRESS_ZONE,
    SUPPRESSING,
    SUPPRESSED,
}

internal enum class DragReleaseAction { SNAP_TO_EDGE, SUPPRESS }

internal class OverlayInteractionMachine {
    var state: OverlayInteractionState = OverlayInteractionState.VISIBLE
        private set

    fun beginDrag() {
        if (state == OverlayInteractionState.VISIBLE) state = OverlayInteractionState.DRAGGING
    }

    /** Returns true only when the pointer enters the suppression zone. */
    fun updateSuppressionTarget(overTarget: Boolean): Boolean {
        if (state !in setOf(OverlayInteractionState.DRAGGING, OverlayInteractionState.DRAGGING_OVER_SUPPRESS_ZONE)) {
            return false
        }
        val entered = overTarget && state != OverlayInteractionState.DRAGGING_OVER_SUPPRESS_ZONE
        state = if (overTarget) OverlayInteractionState.DRAGGING_OVER_SUPPRESS_ZONE else OverlayInteractionState.DRAGGING
        return entered
    }

    fun release(): DragReleaseAction {
        val action = if (state == OverlayInteractionState.DRAGGING_OVER_SUPPRESS_ZONE) {
            state = OverlayInteractionState.SUPPRESSING
            DragReleaseAction.SUPPRESS
        } else {
            state = OverlayInteractionState.VISIBLE
            DragReleaseAction.SNAP_TO_EDGE
        }
        return action
    }

    fun suppressionCompleted() {
        if (state == OverlayInteractionState.SUPPRESSING) state = OverlayInteractionState.SUPPRESSED
    }

    fun reset() {
        state = OverlayInteractionState.VISIBLE
    }
}

internal fun isOverSuppressionTarget(pet: OverlayRect, target: OverlayRect): Boolean {
    val centerX = pet.left + pet.width / 2
    val centerY = pet.top + pet.height / 2
    return centerX in target.left..target.right && centerY in target.top..target.bottom
}

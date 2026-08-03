/*
 * Copyright (C) 2026 DevEmperor (Dictate)
 * Modifications copyright (C) 2026 Gru Contributors
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 */

package com.pguillen.gru.overlay

import android.animation.ValueAnimator
import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.PixelFormat
import android.graphics.PorterDuff
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.util.Log
import android.util.TypedValue
import android.view.Gravity
import android.view.MotionEvent
import android.view.View
import android.view.ViewConfiguration
import android.view.WindowManager
import android.view.animation.DecelerateInterpolator
import android.widget.FrameLayout
import android.widget.TextView
import android.widget.Toast
import androidx.core.content.ContextCompat
import com.pguillen.gru.R
import com.pguillen.gru.GruPet
import com.pguillen.gru.GruPetSize
import com.pguillen.gru.GruPreferences
import com.pguillen.gru.mascot.CustomMascotStore
import com.pguillen.gru.mascot.MascotRuntimeState
import com.pguillen.gru.mascot.MascotSource
import com.pguillen.gru.mascot.MascotVisualResolver
import com.pguillen.gru.dictation.GruDictation
import com.pguillen.gru.dictation.GruDictationFailure
import com.pguillen.gru.dictation.GruDictationState
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.launch
import kotlin.math.hypot

/** Owns Gru's draggable accessibility overlay and renders the current dictation state. */
class GruPetOverlayController(private val service: GruAccessibilityService) {
    private val context: Context get() = service
    private val windowManager = service.getSystemService(Context.WINDOW_SERVICE) as WindowManager
    private val scope = CoroutineScope(Dispatchers.Main.immediate + SupervisorJob())
    private val prefs = GruPreferences.get(context)

    private var rootView: FrameLayout? = null
    private var petView: LivingPetView? = null
    private var signalView: PetSignalView? = null
    private var recordingStatus: TextView? = null
    private var params: WindowManager.LayoutParams? = null
    private var added = false
    private var desiredVisible = false
    private val attachment = OverlayAttachmentTracker()
    private var attachWatchdog: Job? = null
    private var recoveryJob: Job? = null
    private var viewGeneration = 0

    private var currentSource: MascotSource = MascotSource.BuiltIn(GruPet.FAISCA)
    private val visualResolver by lazy { MascotVisualResolver(CustomMascotStore(context)) }
    private var currentSize = GruPetSize.MEDIUM
    private var currentOpacity = 100
    private var previousState: GruDictationState = GruDictationState.Idle
    private var currentRuntimeState = MascotRuntimeState.IDLE
    private var currentPackage: String? = null
    private var previousVisibility: VisibilitySnapshot? = null
    private val positions = mutableMapOf<String, Pair<Int, Int>>()
    private var snapAnimator: ValueAnimator? = null

    private data class Appearance(
        val source: MascotSource,
        val size: GruPetSize,
        val opacity: Int,
    )

    private data class TargetState(
        val editableFocused: Boolean,
        val imeVisible: Boolean,
    )

    private data class VisibilitySnapshot(
        val enabled: Boolean,
        val engineReady: Boolean,
        val editableFocused: Boolean,
        val imeVisible: Boolean,
        val shouldShow: Boolean,
    )

    fun start() {
        scope.launch {
            GruAccessibilityService.foregroundPackage.collect(::onForegroundPackageChanged)
        }
        scope.launch {
            val appearance = combine(
                prefs.mascotSource,
                prefs.size,
                prefs.opacity,
            ) { source, size, opacity -> Appearance(source, size, opacity.coerceIn(40, 100)) }
            val target = combine(
                GruAccessibilityService.editableFocused,
                GruAccessibilityService.imeVisible,
            ) { focused, imeVisible -> TargetState(focused, imeVisible) }
            combine(
                prefs.enabled,
                prefs.engine,
                appearance,
                target,
                GruDictation.state(context),
            ) { enabled, engine, visual, targetState, dictationState ->
                update(enabled, engine != null, visual, targetState, dictationState)
            }.collect { }
        }
    }

    fun destroy() {
        attachWatchdog?.cancel()
        recoveryJob?.cancel()
        scope.cancel()
        snapAnimator?.cancel()
        GruDictation.cancel()
        removeImmediately()
        releasePet()
        service.stopMicForeground()
    }

    fun retry() {
        recoveryJob?.cancel()
        attachment.detach()
        reportAttachment("manual retry")
        rebuildView()
    }

    private fun update(
        enabled: Boolean,
        engineReady: Boolean,
        appearance: Appearance,
        target: TargetState,
        state: GruDictationState,
    ) {
        val nextRuntimeState = runtimeState(state)
        if (appearance.source != currentSource ||
            appearance.size != currentSize ||
            appearance.opacity != currentOpacity
        ) {
            currentSource = appearance.source
            currentSize = appearance.size
            currentOpacity = appearance.opacity
            currentRuntimeState = nextRuntimeState
            rebuildView()
        }
        if (currentSource is MascotSource.Custom && nextRuntimeState != currentRuntimeState) {
            currentRuntimeState = nextRuntimeState
            rebuildView()
        }

        val targetAvailable = target.editableFocused && target.imeVisible
        if (!targetAvailable && state is GruDictationState.Recording) GruDictation.cancel()
        val shouldShow = PetVisibilityPolicy.shouldShow(
            enabled = enabled,
            engineReady = engineReady,
            editableFocused = target.editableFocused,
            imeVisible = target.imeVisible,
        )
        reportVisibility(enabled, engineReady, target, shouldShow)
        if (shouldShow) {
            ensureShown()
            clampPosition()
        } else {
            hide()
        }
        renderState(state)
        manageForeground(state)
        rootView?.keepScreenOn = state is GruDictationState.Recording
        reportError(state)
        previousState = state
    }

    private fun ensureShown() {
        desiredVisible = true
        val view = rootView ?: createView().also { rootView = it }
        if (added) {
            view.animate().cancel()
            view.alpha = 1f
            view.scaleX = 1f
            view.scaleY = 1f
            if (attachment.state == OverlayAttachmentState.Failed) scheduleRecovery()
            return
        }
        val layout = params ?: createParams().also { params = it }
        view.animate().cancel()
        view.alpha = 1f
        view.scaleX = 1f
        view.scaleY = 1f
        attachment.beginAttach()
        reportAttachment("add requested")
        runCatching {
            windowManager.addView(view, layout)
            added = true
            scheduleFirstFrameWatchdog()
        }.onFailure { error ->
            markAttachmentFailed("add failed", error)
        }
    }

    private fun hide() {
        desiredVisible = false
        recoveryJob?.cancel()
        recoveryJob = null
        removeImmediately()
    }

    private fun removeImmediately(resetAttempts: Boolean = true) {
        attachWatchdog?.cancel()
        attachWatchdog = null
        rootView?.animate()?.cancel()
        if (added) rootView?.let { runCatching { windowManager.removeView(it) } }
        added = false
        rootView?.alpha = 1f
        rootView?.scaleX = 1f
        rootView?.scaleY = 1f
        attachment.detach(resetAttempts)
        reportAttachment("removed")
    }

    private fun rebuildView() {
        val wasVisible = desiredVisible
        removeImmediately()
        releasePet()
        rootView = null
        if (wasVisible) ensureShown()
    }

    private fun createView(): FrameLayout {
        val viewSize = scaledDp(96)
        val petSize = scaledDp(86)
        val accent = ContextCompat.getColor(context, R.color.gru_pet_accent)
        val signal = PetSignalView(
            context = context,
            accentColor = accent,
            recordingColor = ContextCompat.getColor(context, R.color.gru_pet_recording),
            successColor = ContextCompat.getColor(context, R.color.gru_pet_success),
            errorColor = ContextCompat.getColor(context, R.color.colorError),
        ).also { signalView = it }
        val generation = ++viewGeneration
        val pet = LivingPetView(context, visualResolver.resolve(currentSource, currentRuntimeState)) {
            onFirstFrame(generation)
        }.apply {
            alpha = currentOpacity / 100f
        }.also { petView = it }
        val status = TextView(context).apply {
            setTextColor(Color.WHITE)
            setTextSize(TypedValue.COMPLEX_UNIT_SP, 10f)
            setTypeface(typeface, Typeface.BOLD)
            gravity = Gravity.CENTER
            includeFontPadding = false
            maxLines = 1
            background = roundedRect(
                ContextCompat.getColor(context, R.color.gru_pet_recording),
                scaledDp(10).toFloat(),
            )
            elevation = scaledDp(5).toFloat()
            visibility = View.GONE
        }.also { recordingStatus = it }

        return PetOverlayLayout(context).apply {
            minimumWidth = viewSize
            minimumHeight = viewSize
            isClickable = true
            isFocusable = true
            addView(signal, FrameLayout.LayoutParams(petSize, petSize, Gravity.BOTTOM or Gravity.CENTER_HORIZONTAL))
            addView(pet, FrameLayout.LayoutParams(petSize, petSize, Gravity.BOTTOM or Gravity.CENTER_HORIZONTAL))
            addView(status, FrameLayout.LayoutParams(scaledDp(90), scaledDp(21), Gravity.TOP or Gravity.CENTER_HORIZONTAL))
            setOnClickListener { onTap() }
            setOnTouchListener(createTouchListener())
        }
    }

    private fun onFirstFrame(generation: Int) {
        if (generation != viewGeneration || !desiredVisible || !added) return
        attachWatchdog?.cancel()
        attachWatchdog = null
        attachment.markVisible()
        reportAttachment("first frame")
    }

    private fun scheduleFirstFrameWatchdog() {
        attachWatchdog?.cancel()
        attachWatchdog = scope.launch {
            delay(FIRST_FRAME_TIMEOUT_MILLIS)
            if (desiredVisible && added && attachment.state == OverlayAttachmentState.Attaching) {
                markAttachmentFailed("first frame timeout")
            }
        }
    }

    private fun markAttachmentFailed(reason: String, error: Throwable? = null) {
        attachWatchdog?.cancel()
        attachWatchdog = null
        attachment.markFailed()
        reportAttachment(reason)
        if (error != null) Log.w(TAG, "$reason: ${error.javaClass.simpleName}")
        scheduleRecovery()
    }

    private fun scheduleRecovery() {
        if (!desiredVisible || recoveryJob?.isActive == true) return
        if (!attachment.reserveRecovery()) {
            reportAttachment("recovery exhausted")
            return
        }
        reportAttachment("recovery scheduled")
        recoveryJob = scope.launch {
            delay(RECOVERY_DELAY_MILLIS)
            if (!desiredVisible) return@launch
            removeImmediately(resetAttempts = false)
            releasePet()
            rootView = null
            ensureShown()
        }
    }

    private fun reportAttachment(reason: String) {
        GruOverlayHealth.overlayChanged(attachment.state, attachment.recoveryAttempts)
        Log.d(TAG, "state=${attachment.state} attempt=${attachment.recoveryAttempts} reason=$reason")
    }

    private fun reportVisibility(
        enabled: Boolean,
        engineReady: Boolean,
        target: TargetState,
        shouldShow: Boolean,
    ) {
        val current = VisibilitySnapshot(
            enabled = enabled,
            engineReady = engineReady,
            editableFocused = target.editableFocused,
            imeVisible = target.imeVisible,
            shouldShow = shouldShow,
        )
        if (current == previousVisibility) return
        previousVisibility = current
        Log.d(
            TAG,
            "visibility enabled=$enabled engineReady=$engineReady " +
                "editableFocused=${target.editableFocused} imeVisible=${target.imeVisible} shouldShow=$shouldShow",
        )
    }

    private fun releasePet() {
        petView?.release()
        signalView?.release()
        petView = null
        signalView = null
        recordingStatus = null
    }

    private fun renderState(state: GruDictationState) {
        val mode = when (state) {
            GruDictationState.Idle -> PetMotionMode.IDLE
            is GruDictationState.Recording -> PetMotionMode.LISTENING
            GruDictationState.Transcribing -> PetMotionMode.PROCESSING
            GruDictationState.Success -> PetMotionMode.SUCCESS
            is GruDictationState.Error -> PetMotionMode.ERROR
        }
        petView?.setMode(mode)
        signalView?.setMode(mode)
        rootView?.contentDescription = context.getString(descriptionFor(state))
        if (state is GruDictationState.Recording) {
            petView?.setAudioLevel(state.audioLevel)
            signalView?.setAudioLevel(state.audioLevel)
            recordingStatus?.apply {
                visibility = View.VISIBLE
                text = context.getString(R.string.gru__pet_recording_label, formatElapsed(state.elapsedMillis))
            }
        } else {
            recordingStatus?.visibility = View.GONE
            petView?.setAudioLevel(0f)
            signalView?.setAudioLevel(0f)
        }
    }

    private fun reportError(state: GruDictationState) {
        if (state !is GruDictationState.Error || state == previousState) return
        Toast.makeText(context, errorMessage(state.reason), Toast.LENGTH_LONG).show()
    }

    private fun errorMessage(reason: GruDictationFailure): String = when (reason) {
        GruDictationFailure.ENGINE_NOT_SELECTED -> context.getString(R.string.gru__error_engine_not_selected)
        GruDictationFailure.MISSING_API_KEY -> context.getString(R.string.gru__error_no_api_key)
        GruDictationFailure.LOCAL_MODEL_MISSING -> context.getString(R.string.gru__error_local_model_missing)
        GruDictationFailure.LOCAL_RUNTIME -> context.getString(R.string.gru__error_local_runtime)
        GruDictationFailure.NO_SPEECH -> context.getString(R.string.gru__no_speech_detected)
        GruDictationFailure.MICROPHONE_PERMISSION -> context.getString(R.string.gru__error_microphone_permission)
        GruDictationFailure.MICROPHONE_UNAVAILABLE -> context.getString(R.string.gru__error_microphone_unavailable)
        GruDictationFailure.NETWORK -> context.getString(R.string.gru__error_network)
        GruDictationFailure.PROVIDER -> context.getString(R.string.gru__error_provider)
        GruDictationFailure.EMPTY_RESPONSE -> context.getString(R.string.gru__error_empty_response)
        GruDictationFailure.INSERTION_REJECTED -> context.getString(R.string.gru__error_insertion)
        GruDictationFailure.UNKNOWN -> context.getString(R.string.gru__error_unknown)
    }

    private fun descriptionFor(state: GruDictationState): Int = when (state) {
        GruDictationState.Idle -> R.string.gru__pet_idle_description
        is GruDictationState.Recording -> R.string.gru__pet_recording_description
        GruDictationState.Transcribing -> R.string.gru__pet_processing_description
        GruDictationState.Success -> R.string.gru__pet_success_description
        is GruDictationState.Error -> R.string.gru__pet_error_description
    }

    private fun manageForeground(state: GruDictationState) {
        when (state) {
            is GruDictationState.Recording -> Unit
            else -> service.stopMicForeground()
        }
    }

    private fun onTap() {
        val state = GruDictation.state(context).value
        if (state !is GruDictationState.Recording && state !is GruDictationState.Transcribing) {
            service.startMicForeground()
        }
        GruDictation.onPetTapped(context)
    }

    private fun createTouchListener(): View.OnTouchListener {
        val slop = ViewConfiguration.get(context).scaledTouchSlop
        var downRawX = 0f
        var downRawY = 0f
        var startX = 0
        var startY = 0
        var dragging = false
        return View.OnTouchListener { _, event ->
            val layout = params ?: return@OnTouchListener false
            when (event.actionMasked) {
                MotionEvent.ACTION_DOWN -> {
                    snapAnimator?.cancel()
                    downRawX = event.rawX
                    downRawY = event.rawY
                    startX = layout.x
                    startY = layout.y
                    dragging = false
                    true
                }
                MotionEvent.ACTION_MOVE -> {
                    val dx = event.rawX - downRawX
                    val dy = event.rawY - downRawY
                    if (!dragging && hypot(dx.toDouble(), dy.toDouble()) >= slop) dragging = true
                    if (dragging) {
                        layout.x = (startX + dx.toInt()).coerceIn(0, maxX())
                        layout.y = (startY + dy.toInt()).coerceIn(minY(), maxY())
                        updateWindowLayout()
                    }
                    true
                }
                MotionEvent.ACTION_UP -> {
                    if (dragging) snapToEdge() else rootView?.performClick()
                    true
                }
                MotionEvent.ACTION_CANCEL -> true
                else -> false
            }
        }
    }

    private fun snapToEdge() {
        val layout = params ?: return
        val target = if (layout.x + rootWidth() / 2 < screenWidth() / 2) EDGE_MARGIN else maxX() - EDGE_MARGIN
        val start = layout.x
        if (!animationsEnabled() || start == target) {
            layout.x = target.coerceIn(0, maxX())
            updateWindowLayout()
            saveCurrentPosition()
            return
        }
        snapAnimator?.cancel()
        snapAnimator = ValueAnimator.ofInt(start, target.coerceIn(0, maxX())).apply {
            duration = 180L
            interpolator = DecelerateInterpolator()
            addUpdateListener {
                layout.x = it.animatedValue as Int
                updateWindowLayout()
            }
            addListener(onEnd = ::saveCurrentPosition)
            start()
        }
    }

    private fun createParams(): WindowManager.LayoutParams {
        val width = scaledDp(96)
        return WindowManager.LayoutParams(
            WindowManager.LayoutParams.WRAP_CONTENT,
            WindowManager.LayoutParams.WRAP_CONTENT,
            WindowManager.LayoutParams.TYPE_ACCESSIBILITY_OVERLAY,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or
                WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS or
                WindowManager.LayoutParams.FLAG_HARDWARE_ACCELERATED,
            PixelFormat.TRANSLUCENT,
        ).apply {
            gravity = Gravity.TOP or Gravity.START
            x = (screenWidth() - width - EDGE_MARGIN).coerceAtLeast(0)
            y = ((service.editorAreaBottom() - width) / 2).coerceIn(minY(), maxY())
        }
    }

    private fun onForegroundPackageChanged(packageName: String?) {
        if (packageName.isNullOrBlank() || packageName == currentPackage) return
        saveCurrentPosition()
        currentPackage = packageName
        val saved = positions[packageName]
        params?.let { layout ->
            if (saved != null) {
                layout.x = saved.first.coerceIn(0, maxX())
                layout.y = saved.second.coerceIn(minY(), maxY())
            } else {
                layout.x = (maxX() - EDGE_MARGIN).coerceAtLeast(0)
                layout.y = ((service.editorAreaBottom() - rootHeight()) / 2).coerceIn(minY(), maxY())
            }
            updateWindowLayout()
        }
    }

    private fun saveCurrentPosition() {
        val packageName = currentPackage ?: return
        val layout = params ?: return
        positions[packageName] = layout.x to layout.y
    }

    private fun updateWindowLayout() {
        if (added) rootView?.let { view -> params?.let { runCatching { windowManager.updateViewLayout(view, it) } } }
    }

    private fun clampPosition() {
        val layout = params ?: return
        val x = layout.x.coerceIn(0, maxX())
        val y = layout.y.coerceIn(minY(), maxY())
        if (layout.x == x && layout.y == y) return
        layout.x = x
        layout.y = y
        updateWindowLayout()
    }

    private fun runtimeState(state: GruDictationState): MascotRuntimeState = when (state) {
        GruDictationState.Idle, is GruDictationState.Success, is GruDictationState.Error -> MascotRuntimeState.IDLE
        is GruDictationState.Recording -> MascotRuntimeState.RECORDING
        is GruDictationState.Transcribing -> MascotRuntimeState.TRANSCRIBING
    }

    private fun roundedRect(color: Int, radius: Float) = GradientDrawable().apply {
        shape = GradientDrawable.RECTANGLE
        cornerRadius = radius
        setColor(color)
    }

    private fun formatElapsed(milliseconds: Long): String {
        val totalSeconds = (milliseconds / 1_000L).coerceAtLeast(0L)
        return "%02d:%02d".format(totalSeconds / 60L, totalSeconds % 60L)
    }

    private fun scaledDp(value: Int): Int =
        (value * currentSize.scale * context.resources.displayMetrics.density).toInt()

    private fun rootWidth(): Int = rootView?.width?.takeIf { it > 0 } ?: scaledDp(96)
    private fun rootHeight(): Int = rootView?.height?.takeIf { it > 0 } ?: scaledDp(96)
    private fun screenWidth(): Int = context.resources.displayMetrics.widthPixels
    private fun screenHeight(): Int = context.resources.displayMetrics.heightPixels
    private fun maxX(): Int = (screenWidth() - rootWidth()).coerceAtLeast(0)
    private fun minY(): Int = EDGE_MARGIN
    private fun maxY(): Int = (service.editorAreaBottom() - rootHeight() - EDGE_MARGIN).coerceAtLeast(minY())

    private fun animationsEnabled(): Boolean = ValueAnimator.areAnimatorsEnabled()

    private fun ValueAnimator.addListener(onEnd: () -> Unit) {
        addListener(object : android.animation.AnimatorListenerAdapter() {
            override fun onAnimationEnd(animation: android.animation.Animator) = onEnd()
        })
    }

    private companion object {
        const val TAG = "GruPetOverlay"
        const val EDGE_MARGIN = 12
        const val FIRST_FRAME_TIMEOUT_MILLIS = 750L
        const val RECOVERY_DELAY_MILLIS = 120L
    }

    private class PetOverlayLayout(context: Context) : FrameLayout(context) {
        override fun dispatchDraw(canvas: Canvas) {
            canvas.drawColor(Color.TRANSPARENT, PorterDuff.Mode.CLEAR)
            super.dispatchDraw(canvas)
        }
    }
}

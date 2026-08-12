/*
 * Copyright (C) 2026 DevEmperor (Dictate)
 * Modifications copyright (C) 2026 Gru Contributors
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 */

package com.pguillen.gru.overlay

import android.accessibilityservice.AccessibilityService
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import android.graphics.Rect
import android.util.Log
import android.view.WindowInsets
import android.view.WindowManager
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo
import android.view.accessibility.AccessibilityWindowInfo
import android.view.inputmethod.InputMethodManager
import com.pguillen.gru.R
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/** Detects the active editor and inserts Gru's finished transcript at its cursor. */
class GruAccessibilityService : AccessibilityService() {
    private val mainHandler = Handler(Looper.getMainLooper())
    private val focusUpdate = Runnable(::updateEditorState)
    private val conversationResolver: ConversationContextResolver = StructuralConversationContextResolver()
    private var bubble: GruPetOverlayController? = null
    private var foreground = false
    private var windowGeneration = 0L

    override fun onServiceConnected() {
        super.onServiceConnected()
        instance = this
        GruOverlayHealth.serviceConnected()
        conversationResolver.startSession()
        ConversationSuppressionSession.startSession(SystemClock.elapsedRealtimeNanos())
        createNotificationChannel()
        bubble = GruPetOverlayController(this).also(GruPetOverlayController::start)
        refreshEditorStateAfterImeSettles()
        Log.d(TAG, "Accessibility service connected")
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        when (event?.eventType) {
            AccessibilityEvent.TYPE_VIEW_TEXT_SELECTION_CHANGED -> {
                mainHandler.removeCallbacks(focusUpdate)
                mainHandler.postDelayed(focusUpdate, FOCUS_UPDATE_DEBOUNCE_MILLIS)
            }
            AccessibilityEvent.TYPE_VIEW_FOCUSED,
            AccessibilityEvent.TYPE_VIEW_CLICKED,
            -> {
                refreshEditorStateAfterImeSettles()
            }
            AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED,
            AccessibilityEvent.TYPE_WINDOWS_CHANGED,
            -> {
                val eventPackage = event.packageName?.toString()
                val foreground = mutableForegroundPackage.value
                if (!eventPackage.isNullOrBlank() && eventPackage != packageName &&
                    (foreground == null || eventPackage == foreground)
                ) windowGeneration += 1L
                refreshEditorStateAfterImeSettles()
            }
        }
    }

    override fun onInterrupt() = Unit

    override fun onUnbind(intent: Intent?): Boolean {
        clearInstance()
        return super.onUnbind(intent)
    }

    override fun onDestroy() {
        clearInstance()
        super.onDestroy()
    }

    private fun updateEditorState() {
        val editable = focusedEditableNode()
        val applicationWindow = focusedApplicationWindow()
        val foreground = currentAppPackage(applicationWindow)?.takeIf { it != packageName }
        mutableEditableFocused.value = editable != null
        mutableImeVisible.value = isImeWindowShown()
        mutableForegroundPackage.value = foreground
        mutableOverlayEnvironment.value = resolveOverlayEnvironment(editable)
        mutableConversationContext.value = conversationResolver.resolve(
            conversationStructure(foreground, applicationWindow, editable),
        )
    }

    private fun refreshEditorStateAfterImeSettles() {
        mainHandler.removeCallbacks(focusUpdate)
        updateEditorState()
        mainHandler.postDelayed(focusUpdate, IME_SETTLE_MILLIS)
    }

    private fun focusedEditableNode(): AccessibilityNodeInfo? {
        editableFrom(findFocus(AccessibilityNodeInfo.FOCUS_INPUT))?.let { return it }
        return windows
            .asSequence()
            .filter { it.type == AccessibilityWindowInfo.TYPE_APPLICATION }
            .sortedByDescending { it.isFocused }
            .mapNotNull { window -> editableFrom(window.root?.findFocus(AccessibilityNodeInfo.FOCUS_INPUT)) }
            .firstOrNull()
    }

    private fun focusedApplicationWindow(): AccessibilityWindowInfo? = runCatching {
        windows.filter { it.type == AccessibilityWindowInfo.TYPE_APPLICATION }
            .maxByOrNull { if (it.isFocused) 1 else 0 }
    }.getOrNull()

    private fun editableFrom(node: AccessibilityNodeInfo?): AccessibilityNodeInfo? = when {
        node == null -> null
        node.isLikelyEditable() -> node
        else -> findEditableDescendant(node, depth = 0)
    }

    private fun activeWindowEditable(): AccessibilityNodeInfo? = focusedEditableNode()

    private fun findEditableDescendant(node: AccessibilityNodeInfo, depth: Int): AccessibilityNodeInfo? {
        if (depth >= MAX_EDITABLE_SEARCH_DEPTH) return null
        repeat(node.childCount) { index ->
            val child = node.getChild(index) ?: return@repeat
            if (child.isLikelyEditable()) return child
            findEditableDescendant(child, depth + 1)?.let { return it }
        }
        return null
    }

    private fun AccessibilityNodeInfo.isLikelyEditable(): Boolean {
        if (isPassword) return false
        if (isEditable) return true
        if (className?.toString()?.contains("EditText") == true) return true
        return actionList.contains(AccessibilityNodeInfo.AccessibilityAction.ACTION_SET_TEXT) &&
            (isFocused || isFocusable)
    }

    private fun isImeWindowShown(): Boolean {
        if (runCatching { windows.any { it.type == AccessibilityWindowInfo.TYPE_INPUT_METHOD } }.getOrDefault(false)) {
            return true
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            val insetsVisible = runCatching {
                getSystemService(WindowManager::class.java)
                    ?.currentWindowMetrics
                    ?.windowInsets
                    ?.isVisible(WindowInsets.Type.ime()) == true
            }.getOrDefault(false)
            if (insetsVisible) return true
        }
        return runCatching {
            getSystemService(InputMethodManager::class.java)?.isAcceptingText == true
        }.getOrDefault(false)
    }

    private fun currentAppPackage(window: AccessibilityWindowInfo?): String? = runCatching {
        window?.root?.packageName?.toString()
            ?: rootInActiveWindow?.packageName?.toString()
    }.getOrNull()

    private fun resolveOverlayEnvironment(editable: AccessibilityNodeInfo?): OverlayEnvironment {
        val usable = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            val metrics = getSystemService(WindowManager::class.java)?.currentWindowMetrics
            val screen = metrics?.bounds
                ?: Rect(0, 0, resources.displayMetrics.widthPixels, resources.displayMetrics.heightPixels)
            val insets = metrics?.windowInsets?.getInsetsIgnoringVisibility(
                WindowInsets.Type.systemBars() or WindowInsets.Type.displayCutout(),
            )
            OverlayRect(
                left = screen.left + (insets?.left ?: 0),
                top = screen.top + (insets?.top ?: 0),
                right = screen.right - (insets?.right ?: 0),
                bottom = screen.bottom - (insets?.bottom ?: 0),
            )
        } else {
            OverlayRect(
                left = 0,
                top = 0,
                right = resources.displayMetrics.widthPixels,
                bottom = resources.displayMetrics.heightPixels,
            )
        }
        val regions = buildList {
            imeBounds()?.takeIf { it.hasArea() }?.let { add(AvoidanceRegion(it, AvoidanceKind.IME)) }
            nodeBounds(editable)?.takeIf { it.hasArea() }?.let { add(AvoidanceRegion(it, AvoidanceKind.EDITOR)) }
        }
        return OverlayEnvironment(usable, regions)
    }

    private fun imeBounds(): OverlayRect? = runCatching {
        val bounds = Rect()
        val ime = windows.firstOrNull { it.type == AccessibilityWindowInfo.TYPE_INPUT_METHOD } ?: return@runCatching null
        ime.getBoundsInScreen(bounds)
        bounds.toOverlayRect()
    }.getOrNull()

    private fun nodeBounds(node: AccessibilityNodeInfo?): OverlayRect? = runCatching {
        node ?: return@runCatching null
        val bounds = Rect()
        node.getBoundsInScreen(bounds)
        bounds.toOverlayRect()
    }.getOrNull()

    private fun conversationStructure(
        foregroundPackage: String?,
        window: AccessibilityWindowInfo?,
        editor: AccessibilityNodeInfo?,
    ): ConversationStructure? = runCatching {
        val packageName = foregroundPackage ?: return@runCatching null
        val activeWindow = window ?: return@runCatching null
        val editable = editor ?: return@runCatching null
        val root = activeWindow.root ?: return@runCatching null
        ConversationStructure(
            packageName = packageName,
            windowId = activeWindow.id,
            windowGeneration = windowGeneration,
            rootUniqueId = root.safeUniqueId(),
            rootViewId = root.viewIdResourceName,
            rootClassName = root.className?.toString(),
            rootChildCount = root.childCount,
            editorUniqueId = editable.safeUniqueId(),
            editorViewId = editable.viewIdResourceName,
            editorClassName = editable.className?.toString(),
            editorBounds = nodeBounds(editable) ?: return@runCatching null,
        )
    }.getOrNull()

    private fun AccessibilityNodeInfo.safeUniqueId(): String? =
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) uniqueId else null

    private fun Rect.toOverlayRect() = OverlayRect(left, top, right, bottom)
    private fun OverlayRect.hasArea() = width > 0 && height > 0

    private fun insertText(text: String): Boolean {
        if (text.isBlank() || !isImeWindowShown()) return false
        repeat(COMMIT_ATTEMPTS) { attempt ->
            val target = activeWindowEditable() ?: return@repeat
            if (!target.isFocused) {
                runCatching { target.performAction(AccessibilityNodeInfo.ACTION_FOCUS) }
                runCatching { target.refresh() }
                SystemClock.sleep(FOCUS_SETTLE_MILLIS)
            }
            if (commitViaInputConnection(text)) return true
            if (setTextAtSelection(target, text)) return true
            if (pasteAtSelection(target, text)) return true
            if (attempt < COMMIT_ATTEMPTS - 1) SystemClock.sleep(COMMIT_RETRY_MILLIS)
        }
        return false
    }

    private fun commitViaInputConnection(text: String): Boolean {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) return false
        val connection = inputMethod?.currentInputConnection ?: return false
        return runCatching { connection.commitText(text, 1, null) }.isSuccess
    }

    private fun setTextAtSelection(node: AccessibilityNodeInfo, insertion: String): Boolean {
        val existing = node.editableText()
        val from = node.textSelectionStart.coerceForText(existing)
        val to = node.textSelectionEnd.coerceForText(existing)
        val start = minOf(from, to)
        val end = maxOf(from, to)
        val updated = existing.substring(0, start) + insertion + existing.substring(end)
        val setText = Bundle().apply {
            putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, updated)
        }
        if (!node.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, setText)) return false
        val cursor = start + insertion.length
        val selection = Bundle().apply {
            putInt(AccessibilityNodeInfo.ACTION_ARGUMENT_SELECTION_START_INT, cursor)
            putInt(AccessibilityNodeInfo.ACTION_ARGUMENT_SELECTION_END_INT, cursor)
        }
        node.performAction(AccessibilityNodeInfo.ACTION_SET_SELECTION, selection)
        return true
    }

    private fun pasteAtSelection(node: AccessibilityNodeInfo, text: String): Boolean {
        if (!node.actionList.contains(AccessibilityNodeInfo.AccessibilityAction.ACTION_PASTE)) return false
        val clipboard = getSystemService(ClipboardManager::class.java) ?: return false
        val previous = runCatching { clipboard.primaryClip }.getOrNull()
        if (runCatching { clipboard.setPrimaryClip(ClipData.newPlainText("Gru", text)) }.isFailure) return false
        val inserted = node.performAction(AccessibilityNodeInfo.ACTION_PASTE)
        mainHandler.postDelayed({
            runCatching {
                when {
                    previous != null -> clipboard.setPrimaryClip(previous)
                    Build.VERSION.SDK_INT >= Build.VERSION_CODES.P -> clipboard.clearPrimaryClip()
                    else -> clipboard.setPrimaryClip(ClipData.newPlainText("", ""))
                }
            }
        }, CLIPBOARD_RESTORE_MILLIS)
        return inserted
    }

    private fun AccessibilityNodeInfo.editableText(): String {
        val value = text?.toString().orEmpty()
        val hint = hintText?.toString()?.trim()
        return if (!hint.isNullOrEmpty() && value.trim() == hint) "" else value
    }

    private fun Int.coerceForText(text: String): Int = if (this in 0..text.length) this else text.length

    fun startMicForeground() {
        if (foreground) return
        val notification = Notification.Builder(this, NOTIFICATION_CHANNEL)
            .setSmallIcon(R.drawable.ic_gru_microphone)
            .setContentTitle(getString(R.string.gru__app_name))
            .setContentText(getString(R.string.gru__overlay_notification_recording))
            .setOngoing(true)
            .build()
        val foregroundResult = runCatching {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
                startForeground(NOTIFICATION_ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE)
            } else {
                startForeground(NOTIFICATION_ID, notification)
            }
        }
        if (foregroundResult.isFailure) {
            Log.w(TAG, "Foreground promotion unavailable: ${foregroundResult.exceptionOrNull()?.javaClass?.simpleName}")
            getSystemService(NotificationManager::class.java)?.notify(NOTIFICATION_ID, notification)
        }
        foreground = true
    }

    fun stopMicForeground() {
        if (!foreground) return
        runCatching { stopForeground(STOP_FOREGROUND_REMOVE) }
        getSystemService(NotificationManager::class.java)?.cancel(NOTIFICATION_ID)
        foreground = false
    }

    private fun createNotificationChannel() {
        val manager = getSystemService(NotificationManager::class.java) ?: return
        if (manager.getNotificationChannel(NOTIFICATION_CHANNEL) != null) return
        manager.createNotificationChannel(
            NotificationChannel(
                NOTIFICATION_CHANNEL,
                getString(R.string.gru__overlay_notification_channel),
                NotificationManager.IMPORTANCE_LOW,
            ),
        )
    }

    private fun clearInstance() {
        if (instance !== this) return
        instance = null
        mutableEditableFocused.value = false
        mutableImeVisible.value = false
        mutableForegroundPackage.value = null
        mutableOverlayEnvironment.value = defaultOverlayEnvironment()
        mutableConversationContext.value = null
        ConversationSuppressionSession.startSession(0L)
        mainHandler.removeCallbacksAndMessages(null)
        bubble?.destroy()
        bubble = null
        stopMicForeground()
        GruOverlayHealth.serviceDisconnected()
        Log.d(TAG, "Accessibility service disconnected")
    }

    companion object {
        private const val TAG = "GruAccessibility"
        private const val NOTIFICATION_ID = 0xD1C7
        private const val NOTIFICATION_CHANNEL = "gru_recording"
        private const val MAX_EDITABLE_SEARCH_DEPTH = 6
        private const val COMMIT_ATTEMPTS = 2
        private const val COMMIT_RETRY_MILLIS = 60L
        private const val FOCUS_SETTLE_MILLIS = 40L
        private const val FOCUS_UPDATE_DEBOUNCE_MILLIS = 150L
        private const val IME_SETTLE_MILLIS = 500L
        private const val CLIPBOARD_RESTORE_MILLIS = 400L

        @Volatile private var instance: GruAccessibilityService? = null

        private val mutableEditableFocused = MutableStateFlow(false)
        val editableFocused: StateFlow<Boolean> = mutableEditableFocused.asStateFlow()

        private val mutableImeVisible = MutableStateFlow(false)
        val imeVisible: StateFlow<Boolean> = mutableImeVisible.asStateFlow()

        private val mutableForegroundPackage = MutableStateFlow<String?>(null)
        val foregroundPackage: StateFlow<String?> = mutableForegroundPackage.asStateFlow()

        private val mutableOverlayEnvironment = MutableStateFlow(defaultOverlayEnvironment())
        internal val overlayEnvironment: StateFlow<OverlayEnvironment> = mutableOverlayEnvironment.asStateFlow()

        private val mutableConversationContext = MutableStateFlow<ConversationContext?>(null)
        internal val conversationContext: StateFlow<ConversationContext?> = mutableConversationContext.asStateFlow()

        private fun defaultOverlayEnvironment() = OverlayEnvironment(
            usableBounds = OverlayRect(0, 0, 1, 1),
            avoidanceRegions = emptyList(),
        )

        fun injectText(text: String): Boolean = instance?.insertText(text) ?: false

        fun retryOverlay(): Boolean {
            val service = instance ?: return false
            service.bubble?.retry()
            service.refreshEditorStateAfterImeSettles()
            return true
        }
    }
}

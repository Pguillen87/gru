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
import android.util.Log
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo
import android.view.accessibility.AccessibilityWindowInfo
import com.pguillen.gru.R
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/** Detects the active editor and inserts Gru's finished transcript at its cursor. */
class DictateAccessibilityService : AccessibilityService() {
    private val mainHandler = Handler(Looper.getMainLooper())
    private val focusUpdate = Runnable(::updateEditorState)
    private var bubble: DictateBubbleController? = null
    private var foreground = false

    override fun onServiceConnected() {
        super.onServiceConnected()
        instance = this
        createNotificationChannel()
        bubble = DictateBubbleController(this).also(DictateBubbleController::start)
        updateEditorState()
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
            AccessibilityEvent.TYPE_WINDOW_STATE_CHANGED,
            AccessibilityEvent.TYPE_WINDOWS_CHANGED,
            -> {
                mainHandler.removeCallbacks(focusUpdate)
                updateEditorState()
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
        mutableEditableFocused.value = focusedEditableNode() != null
        mutableImeVisible.value = isImeWindowShown()
        currentAppPackage()?.takeIf { it != packageName }?.let { mutableForegroundPackage.value = it }
    }

    private fun focusedEditableNode(): AccessibilityNodeInfo? {
        val node = findFocus(AccessibilityNodeInfo.FOCUS_INPUT) ?: return null
        if (node.isLikelyEditable()) return node
        return findEditableDescendant(node, depth = 0)
    }

    private fun activeWindowEditable(): AccessibilityNodeInfo? {
        val root = rootInActiveWindow ?: return null
        root.findFocus(AccessibilityNodeInfo.FOCUS_INPUT)?.let { focused ->
            if (focused.isLikelyEditable()) return focused
            findEditableDescendant(focused, depth = 0)?.let { return it }
        }
        return root.takeIf { it.isFocused && it.isLikelyEditable() }
    }

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
        if (isEditable) return true
        if (className?.toString()?.contains("EditText") == true) return true
        return actionList.contains(AccessibilityNodeInfo.AccessibilityAction.ACTION_SET_TEXT) &&
            (isFocused || isFocusable)
    }

    private fun isImeWindowShown(): Boolean = runCatching {
        windows.any { it.type == AccessibilityWindowInfo.TYPE_INPUT_METHOD }
    }.getOrDefault(false)

    private fun currentAppPackage(): String? = runCatching {
        windows
            .filter { it.type == AccessibilityWindowInfo.TYPE_APPLICATION }
            .sortedByDescending { it.isFocused }
            .firstOrNull()
            ?.root
            ?.packageName
            ?.toString()
            ?: rootInActiveWindow?.packageName?.toString()
    }.getOrNull()

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
                if (previous != null) clipboard.setPrimaryClip(previous) else clipboard.clearPrimaryClip()
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
            .setSmallIcon(R.drawable.ic_dictate_overlay_mic)
            .setContentTitle(getString(R.string.gru__app_name))
            .setContentText(getString(R.string.dictate__overlay_notification_recording))
            .setOngoing(true)
            .build()
        runCatching {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                startForeground(NOTIFICATION_ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE)
            } else {
                startForeground(NOTIFICATION_ID, notification)
            }
            foreground = true
        }
    }

    fun stopMicForeground() {
        if (!foreground) return
        runCatching { stopForeground(STOP_FOREGROUND_REMOVE) }
        foreground = false
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val manager = getSystemService(NotificationManager::class.java) ?: return
        if (manager.getNotificationChannel(NOTIFICATION_CHANNEL) != null) return
        manager.createNotificationChannel(
            NotificationChannel(
                NOTIFICATION_CHANNEL,
                getString(R.string.dictate__overlay_notification_channel),
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
        mainHandler.removeCallbacksAndMessages(null)
        bubble?.destroy()
        bubble = null
        stopMicForeground()
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
        private const val CLIPBOARD_RESTORE_MILLIS = 400L

        @Volatile private var instance: DictateAccessibilityService? = null

        private val mutableEditableFocused = MutableStateFlow(false)
        val editableFocused: StateFlow<Boolean> = mutableEditableFocused.asStateFlow()

        private val mutableImeVisible = MutableStateFlow(false)
        val imeVisible: StateFlow<Boolean> = mutableImeVisible.asStateFlow()

        private val mutableForegroundPackage = MutableStateFlow<String?>(null)
        val foregroundPackage: StateFlow<String?> = mutableForegroundPackage.asStateFlow()

        fun injectText(text: String): Boolean = instance?.insertText(text) ?: false
    }
}

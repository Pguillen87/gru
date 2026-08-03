/*
 * Copyright (C) 2026 Gru Contributors
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 */

package com.pguillen.gru

import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.ScrollState
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Cloud
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Download
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.Visibility
import androidx.compose.material.icons.filled.VisibilityOff
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedCard
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.foundation.shape.RoundedCornerShape
import com.pguillen.gru.dictation.GruDictation
import com.pguillen.gru.dictation.TranscriptionEngine
import com.pguillen.gru.dictation.TranscriptionSelectionPolicy
import com.pguillen.gru.local.WhisperModelError
import com.pguillen.gru.local.WhisperModelManager
import com.pguillen.gru.local.WhisperModelState

@Composable
internal fun GruTranscriptionScreen(
    prefs: GruPreferences,
    modifier: Modifier = Modifier,
    firstUse: Boolean = false,
    onConfigured: () -> Unit = {},
) {
    val context = LocalContext.current
    val manager = remember { WhisperModelManager.get(context) }
    val current by prefs.engine.collectAsState()
    val requested by prefs.requestedEngine.collectAsState()
    val apiKey by prefs.groqApiKeyState.collectAsState()
    val modelState by manager.state.collectAsState()
    var editKey by remember { mutableStateOf(false) }
    val scrollState = if (firstUse) remember { ScrollState(0) } else rememberScrollState()

    Column(
        modifier.verticalScroll(scrollState).navigationBarsPadding()
            .padding(horizontal = 20.dp, vertical = 16.dp),
        verticalArrangement = Arrangement.spacedBy(24.dp),
    ) {
        if (!firstUse) CurrentEngine(current)
        if (firstUse) {
            Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text(stringResource(R.string.gru__choose_engine_title), style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.SemiBold)
                Text(stringResource(R.string.gru__choose_engine_summary), color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        } else {
            SectionTitle(R.string.gru__change_engine)
        }
        EngineChoice(
            icon = { Icon(Icons.Default.Cloud, null) },
            title = R.string.gru__online_title,
            subtitle = R.string.gru__online_subtitle,
            details = R.string.gru__online_details,
            benefits = R.string.gru__online_benefits,
            active = current == TranscriptionEngine.ONLINE_GROQ,
            configuring = requested == TranscriptionEngine.ONLINE_GROQ && current != TranscriptionEngine.ONLINE_GROQ,
            action = R.string.gru__use_online,
        ) {
            prefs.requestEngine(TranscriptionEngine.ONLINE_GROQ)
            if (apiKey.isBlank()) editKey = true else prefs.setEngine(TranscriptionEngine.ONLINE_GROQ)
        }
        EngineChoice(
            icon = { Icon(Icons.Default.Lock, null) },
            title = R.string.gru__private_title,
            subtitle = R.string.gru__private_subtitle,
            details = R.string.gru__private_details,
            benefits = R.string.gru__private_benefits,
            active = current == TranscriptionEngine.PRIVATE_LOCAL,
            configuring = requested == TranscriptionEngine.PRIVATE_LOCAL && current != TranscriptionEngine.PRIVATE_LOCAL,
            action = if (modelState is WhisperModelState.Installed) {
                R.string.gru__activate_private
            } else {
                R.string.gru__use_private
            },
        ) {
            prefs.requestEngine(TranscriptionEngine.PRIVATE_LOCAL)
            if (TranscriptionSelectionPolicy.canActivate(TranscriptionEngine.PRIVATE_LOCAL, apiKey.isNotBlank(), modelState is WhisperModelState.Installed)) {
                prefs.setEngine(TranscriptionEngine.PRIVATE_LOCAL)
                onConfigured()
            }
        }
        if (requested == TranscriptionEngine.ONLINE_GROQ || current == TranscriptionEngine.ONLINE_GROQ) {
            GroqSettings(apiKey, onEdit = { editKey = true }, onRemove = {
                prefs.removeGroqApiKey()
                if (current == TranscriptionEngine.ONLINE_GROQ) {
                    prefs.setEngine(null)
                }
            })
        }
        if (requested == TranscriptionEngine.PRIVATE_LOCAL || current == TranscriptionEngine.PRIVATE_LOCAL) {
            LocalModelSettings(
                state = modelState,
                onDownload = manager::download,
                onCancel = manager::cancelDownload,
                isActive = current == TranscriptionEngine.PRIVATE_LOCAL,
                onActivate = {
                    prefs.setEngine(TranscriptionEngine.PRIVATE_LOCAL)
                    onConfigured()
                },
                onRemove = {
                    if (current == TranscriptionEngine.PRIVATE_LOCAL) {
                        prefs.setEngine(null)
                    }
                    manager.removeModel(GruDictation::releaseLocalModel)
                },
            )
        }
    }
    if (editKey) GroqKeyDialog(
        onDismiss = { editKey = false },
        onSave = { value ->
            prefs.groqApiKey = value
            if (prefs.groqApiKey == value) {
                prefs.requestEngine(TranscriptionEngine.ONLINE_GROQ)
                prefs.setEngine(TranscriptionEngine.ONLINE_GROQ)
                editKey = false
                onConfigured()
            }
        },
    )
}

@Composable
private fun CurrentEngine(engine: TranscriptionEngine?) {
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text(stringResource(R.string.gru__current_engine), style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(
            stringResource(when (engine) {
                TranscriptionEngine.ONLINE_GROQ -> R.string.gru__engine_online
                TranscriptionEngine.PRIVATE_LOCAL -> R.string.gru__engine_private
                null -> R.string.gru__engine_not_configured
            }),
            style = MaterialTheme.typography.titleLarge,
            fontWeight = FontWeight.SemiBold,
        )
    }
}

@Composable
private fun EngineChoice(
    icon: @Composable () -> Unit,
    title: Int,
    subtitle: Int,
    details: Int,
    benefits: Int,
    active: Boolean,
    configuring: Boolean,
    action: Int,
    onClick: () -> Unit,
) {
    OutlinedCard(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(8.dp),
        border = BorderStroke(1.dp, if (active) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.outlineVariant),
    ) { Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            icon()
            Column(Modifier.weight(1f)) {
                Text(stringResource(title), style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                Text(stringResource(subtitle), style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.primary)
            }
            if (active) Icon(Icons.Default.CheckCircle, stringResource(R.string.gru__active))
        }
        Text(stringResource(benefits), style = MaterialTheme.typography.bodyMedium)
        Text(stringResource(details), style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        when {
            active -> Text(stringResource(R.string.gru__active), color = MaterialTheme.colorScheme.primary, fontWeight = FontWeight.SemiBold)
            configuring -> Text(stringResource(R.string.gru__preparing_mode), color = MaterialTheme.colorScheme.primary, fontWeight = FontWeight.SemiBold)
            else -> OutlinedButton(onClick = onClick, modifier = Modifier.fillMaxWidth()) { Text(stringResource(action)) }
        }
    } }
}

@Composable
private fun GroqSettings(apiKey: String, onEdit: () -> Unit, onRemove: () -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
        SectionTitle(R.string.gru__groq_settings)
        Text(
            stringResource(if (apiKey.isBlank()) R.string.gru__key_missing else R.string.gru__key_saved),
            color = if (apiKey.isBlank()) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.primary,
            fontWeight = FontWeight.SemiBold,
        )
        Text(stringResource(R.string.gru__groq_privacy), style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Button(onClick = onEdit, modifier = Modifier.fillMaxWidth()) {
            Text(stringResource(if (apiKey.isBlank()) R.string.gru__add_key else R.string.gru__change_key))
        }
        if (apiKey.isNotBlank()) TextButton(onClick = onRemove, modifier = Modifier.fillMaxWidth()) {
            Icon(Icons.Default.Delete, null)
            Text(stringResource(R.string.gru__remove_key), modifier = Modifier.padding(start = 8.dp))
        }
    }
}

@Composable
private fun LocalModelSettings(
    state: WhisperModelState,
    onDownload: () -> Unit,
    onCancel: () -> Unit,
    onActivate: () -> Unit,
    onRemove: () -> Unit,
    isActive: Boolean,
) {
    Column(
        modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite },
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        SectionTitle(R.string.gru__offline_model)
        Text(stringResource(R.string.gru__model_name), fontWeight = FontWeight.Medium)
        Text(stringResource(R.string.gru__model_size), color = MaterialTheme.colorScheme.onSurfaceVariant)
        when (state) {
            WhisperModelState.NotInstalled -> {
                Text(stringResource(R.string.gru__model_not_installed))
                Button(onClick = onDownload, modifier = Modifier.fillMaxWidth()) {
                    Icon(Icons.Default.Download, null)
                    Text(stringResource(R.string.gru__download_model), Modifier.padding(start = 8.dp))
                }
            }
            WhisperModelState.Preparing -> ProgressState(R.string.gru__model_preparing)
            is WhisperModelState.Downloading -> {
                val progress = (state.downloadedBytes.toFloat() / state.totalBytes).coerceIn(0f, 1f)
                Text(stringResource(R.string.gru__model_downloading, bytesToMb(state.downloadedBytes), bytesToMb(state.totalBytes)))
                LinearProgressIndicator(progress = { progress }, modifier = Modifier.fillMaxWidth())
                TextButton(onClick = onCancel, modifier = Modifier.fillMaxWidth()) { Text(stringResource(R.string.gru__cancel_download)) }
            }
            WhisperModelState.Verifying -> ProgressState(R.string.gru__model_verifying)
            is WhisperModelState.Installed -> {
                Text(stringResource(R.string.gru__model_installed), color = MaterialTheme.colorScheme.primary, fontWeight = FontWeight.SemiBold)
                if (!isActive) FilledTonalButton(onClick = onActivate, modifier = Modifier.fillMaxWidth()) {
                    Text(stringResource(R.string.gru__activate_private))
                }
                TextButton(onClick = onRemove, modifier = Modifier.fillMaxWidth()) {
                    Icon(Icons.Default.Delete, null)
                    Text(stringResource(R.string.gru__remove_model), Modifier.padding(start = 8.dp))
                }
            }
            is WhisperModelState.Error -> {
                Text(stringResource(modelErrorText(state.reason)), color = MaterialTheme.colorScheme.error)
                Button(onClick = onDownload, modifier = Modifier.fillMaxWidth()) { Text(stringResource(R.string.gru__try_download_again)) }
            }
        }
        Text(stringResource(R.string.gru__model_source), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
private fun ProgressState(label: Int) {
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        CircularProgressIndicator(modifier = Modifier.padding(4.dp))
        Text(stringResource(label))
    }
}

@Composable
private fun GroqKeyDialog(onDismiss: () -> Unit, onSave: (String) -> Unit) {
    val context = LocalContext.current
    var value by remember { mutableStateOf("") }
    var visible by remember { mutableStateOf(false) }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(stringResource(R.string.gru__connect_groq)) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text(stringResource(R.string.gru__connect_groq_summary))
                OutlinedButton(onClick = { openGroqKeys(context) }, modifier = Modifier.fillMaxWidth()) {
                    Text(stringResource(R.string.gru__get_free_key))
                }
                OutlinedTextField(
                    value = value,
                    onValueChange = { value = it },
                    label = { Text(stringResource(R.string.gru__api_key_label)) },
                    supportingText = { Text(stringResource(R.string.gru__api_key_secure_summary)) },
                    singleLine = true,
                    visualTransformation = if (visible) VisualTransformation.None else PasswordVisualTransformation(),
                    trailingIcon = { IconButton(onClick = { visible = !visible }) {
                        Icon(
                            if (visible) Icons.Default.VisibilityOff else Icons.Default.Visibility,
                            stringResource(if (visible) R.string.gru__api_key_hide else R.string.gru__api_key_show),
                        )
                    } },
                )
                TextButton(onClick = { value = clipboardText(context) }, modifier = Modifier.fillMaxWidth()) {
                    Text(stringResource(R.string.gru__paste_key))
                }
            }
        },
        confirmButton = { TextButton(onClick = { onSave(value.trim()) }, enabled = value.isNotBlank()) { Text(stringResource(R.string.gru__save_and_continue)) } },
        dismissButton = { TextButton(onClick = onDismiss) { Text(stringResource(android.R.string.cancel)) } },
    )
}

private fun clipboardText(context: Context): String {
    val clipboard = context.getSystemService(ClipboardManager::class.java)
    return clipboard?.primaryClip?.getItemAt(0)?.coerceToText(context)?.toString().orEmpty().trim()
}

private fun openGroqKeys(context: Context) {
    val intent = Intent(Intent.ACTION_VIEW, Uri.parse(GROQ_KEYS_URL)).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
    runCatching { context.startActivity(intent) }
}

private const val GROQ_KEYS_URL = "https://console.groq.com/keys"

private fun modelErrorText(error: WhisperModelError): Int = when (error) {
    WhisperModelError.INSUFFICIENT_SPACE -> R.string.gru__model_error_space
    WhisperModelError.NETWORK -> R.string.gru__model_error_network
    WhisperModelError.INVALID_SIZE, WhisperModelError.INVALID_CHECKSUM -> R.string.gru__model_error_corrupt
    WhisperModelError.STORAGE -> R.string.gru__model_error_storage
}

private fun bytesToMb(bytes: Long): Long = bytes / (1024L * 1024L)

/*
 * Copyright (C) 2026 Gru Contributors
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 */

package com.pguillen.gru

import android.Manifest
import android.content.Intent
import android.os.Build
import android.provider.Settings
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Image
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Slider
import androidx.compose.material3.Switch
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
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.pguillen.gru.dictation.TranscriptionEngine
import com.pguillen.gru.local.WhisperModelManager
import com.pguillen.gru.local.WhisperModelState
import com.pguillen.gru.overlay.GruAccessibilityService
import com.pguillen.gru.overlay.GruOverlayHealth
import com.pguillen.gru.overlay.GruOverlayHealthState
import com.pguillen.gru.overlay.OverlayAttachmentState

@Composable
internal fun GruGeneralScreen(
    prefs: GruPreferences,
    permissionRefresh: Int,
    onPermissionChanged: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val context = LocalContext.current
    val engine by prefs.engine.collectAsState()
    val key by prefs.groqApiKeyState.collectAsState()
    val modelState by WhisperModelManager.get(context).state.collectAsState()
    val overlayHealth by GruOverlayHealth.state.collectAsState()
    val serviceConnected = overlayHealth.serviceConnected
    val accessibilityReady = remember(permissionRefresh) { isGruAccessibilityEnabled(context) }
    val microphoneReady = remember(permissionRefresh) { hasPermission(context, Manifest.permission.RECORD_AUDIO) }
    val notificationsReady = remember(permissionRefresh) { notificationsAllowed(context) }
    val engineReady = when (engine) {
        TranscriptionEngine.ONLINE_GROQ -> key.isNotBlank()
        TranscriptionEngine.PRIVATE_LOCAL -> modelState is WhisperModelState.Installed
        null -> false
    }

    Column(
        modifier = modifier.verticalScroll(rememberScrollState()).navigationBarsPadding()
            .padding(horizontal = 20.dp, vertical = 16.dp),
        verticalArrangement = Arrangement.spacedBy(24.dp),
    ) {
        StatusSummary(false, accessibilityReady, serviceConnected, microphoneReady, engineReady, overlayHealth)
        PermissionSection(accessibilityReady, microphoneReady, notificationsReady, onPermissionChanged)
        Spacer(Modifier.height(8.dp))
    }
}

@Composable
private fun StatusSummary(
    enabled: Boolean,
    accessibility: Boolean,
    serviceConnected: Boolean,
    microphone: Boolean,
    engine: Boolean,
    overlay: GruOverlayHealthState,
) {
    val title = when {
        !engine -> R.string.gru__status_transcription
        !accessibility -> R.string.gru__status_accessibility
        !serviceConnected -> R.string.gru__status_service_disconnected
        !microphone -> R.string.gru__status_microphone
        !enabled -> R.string.gru__status_enable_pet
        overlay.attachment == OverlayAttachmentState.Failed -> R.string.gru__status_pet_failed
        !overlay.hasRenderedFrame -> R.string.gru__status_pet_testing
        else -> R.string.gru__status_ready
    }
    val summary = when {
        enabled && overlay.attachment == OverlayAttachmentState.Failed -> R.string.gru__pet_runtime_failed
        enabled && overlay.attachment == OverlayAttachmentState.Visible -> R.string.gru__pet_runtime_visible
        enabled && overlay.hasRenderedFrame -> R.string.gru__ready_message
        enabled && accessibility && serviceConnected -> R.string.gru__pet_runtime_ready
        else -> R.string.gru__status_pending_summary
    }
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text(stringResource(title), style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.SemiBold)
        Text(
            stringResource(summary),
            style = MaterialTheme.typography.bodyLarge,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
    }
}

@Composable
private fun PetRuntimeStatus(accessibility: Boolean, serviceConnected: Boolean, health: GruOverlayHealthState) {
    val status = when {
        !accessibility -> R.string.gru__pet_runtime_permission
        !serviceConnected -> R.string.gru__pet_runtime_disconnected
        health.attachment == OverlayAttachmentState.Attaching -> R.string.gru__pet_runtime_attaching
        health.attachment == OverlayAttachmentState.Visible -> R.string.gru__pet_runtime_visible
        health.attachment == OverlayAttachmentState.Failed -> R.string.gru__pet_runtime_failed
        health.hasRenderedFrame -> R.string.gru__pet_runtime_verified
        else -> R.string.gru__pet_runtime_ready
    }
    Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        SectionTitle(R.string.gru__pet_runtime_title)
        Text(
            stringResource(status),
            style = MaterialTheme.typography.bodyMedium,
            color = if (health.attachment == OverlayAttachmentState.Failed) {
                MaterialTheme.colorScheme.error
            } else {
                MaterialTheme.colorScheme.onSurfaceVariant
            },
        )
        if (health.attachment == OverlayAttachmentState.Failed) {
            Button(
                onClick = { GruAccessibilityService.retryOverlay() },
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text(stringResource(R.string.gru__pet_retry))
            }
        }
    }
}

@Composable
private fun PermissionSection(accessibility: Boolean, microphone: Boolean, notifications: Boolean, changed: () -> Unit) {
    val context = LocalContext.current
    var disclosure by remember { mutableStateOf(false) }
    val microphoneLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { changed() }
    val notificationLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { changed() }
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        SectionTitle(R.string.gru__permissions)
        PermissionRow(R.string.gru__accessibility_title, R.string.gru__accessibility_summary, accessibility, R.string.gru__accessibility_action) {
            disclosure = true
        }
        HorizontalDivider()
        PermissionRow(R.string.gru__microphone_title, R.string.gru__microphone_summary, microphone, R.string.gru__microphone_action) {
            microphoneLauncher.launch(Manifest.permission.RECORD_AUDIO)
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            HorizontalDivider()
            PermissionRow(R.string.gru__notifications_title, R.string.gru__notifications_summary, notifications, R.string.gru__notifications_action) {
                notificationLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
            }
        }
    }
    if (disclosure) AlertDialog(
        onDismissRequest = { disclosure = false },
        title = { Text(stringResource(R.string.gru__accessibility_title)) },
        text = { Text(stringResource(R.string.gru__accessibility_summary)) },
        confirmButton = { TextButton(onClick = {
            disclosure = false
            context.startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
        }) { Text(stringResource(R.string.gru__accessibility_action)) } },
        dismissButton = { TextButton(onClick = { disclosure = false }) { Text(stringResource(android.R.string.cancel)) } },
    )
}

@Composable
private fun PermissionRow(title: Int, summary: Int, granted: Boolean, actionLabel: Int, action: () -> Unit) {
    Column(Modifier.fillMaxWidth().padding(vertical = 8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(stringResource(title), style = MaterialTheme.typography.titleSmall)
        Text(
            stringResource(if (granted) R.string.gru__granted else R.string.gru__pending),
            color = if (granted) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.error,
            fontWeight = FontWeight.SemiBold,
        )
        Text(stringResource(summary), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        if (!granted) Button(onClick = action, modifier = Modifier.fillMaxWidth()) { Text(stringResource(actionLabel)) }
    }
}

@Composable
private fun PetPreview(design: GruPet, opacity: Int) {
    val pet = petFor(design)
    Column(Modifier.fillMaxWidth(), horizontalAlignment = Alignment.CenterHorizontally) {
        Image(
            painterResource(pet.drawable),
            stringResource(R.string.gru__preview_description, stringResource(pet.name)),
            contentScale = ContentScale.Fit,
            modifier = Modifier.size(132.dp).alpha(opacity.coerceIn(40, 100) / 100f),
        )
        Text(stringResource(R.string.gru__tagline), style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.SemiBold)
    }
}

@Composable
private fun MasterToggle(enabled: Boolean, ready: Boolean, onChange: (Boolean) -> Unit) {
    Row(Modifier.fillMaxWidth(), Arrangement.SpaceBetween, Alignment.CenterVertically) {
        Column(Modifier.weight(1f).padding(end = 16.dp)) {
            Text(stringResource(R.string.gru__pet_enabled), style = MaterialTheme.typography.titleMedium)
            Text(stringResource(R.string.gru__pet_enabled_summary), style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Switch(checked = enabled, onCheckedChange = onChange, enabled = ready)
    }
}

@Composable
private fun PetPicker(selected: GruPet, onSelect: (GruPet) -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        SectionTitle(R.string.gru__choose_pet)
        PETS.chunked(3).forEach { pets ->
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                pets.forEach { pet -> PetChoice(pet, selected == pet.design, Modifier.weight(1f)) { onSelect(pet.design) } }
                repeat(3 - pets.size) { Spacer(Modifier.weight(1f)) }
            }
        }
    }
}

@Composable
private fun PetChoice(pet: PetOption, selected: Boolean, modifier: Modifier, onClick: () -> Unit) {
    val color = if (selected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.outlineVariant
    Column(
        modifier.semantics { this.selected = selected; role = Role.RadioButton }
            .border(if (selected) 2.dp else 1.dp, color, RoundedCornerShape(8.dp))
            .clickable(onClick = onClick).padding(vertical = 8.dp, horizontal = 4.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Image(painterResource(pet.drawable), null, modifier = Modifier.size(52.dp))
        Text(stringResource(pet.name), style = MaterialTheme.typography.labelMedium, maxLines = 1)
    }
}

@Composable
private fun AppearanceControls(size: GruPetSize, opacity: Int, prefs: GruPreferences) {
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        SectionTitle(R.string.gru__appearance)
        Text(stringResource(R.string.gru__size), style = MaterialTheme.typography.bodyLarge)
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            SizeChip(R.string.gru__size_small, GruPetSize.SMALL, size, prefs)
            SizeChip(R.string.gru__size_medium, GruPetSize.MEDIUM, size, prefs)
            SizeChip(R.string.gru__size_large, GruPetSize.LARGE, size, prefs)
        }
        Text(stringResource(R.string.gru__opacity, opacity), style = MaterialTheme.typography.bodyLarge)
        Slider(opacity.toFloat(), { prefs.setOpacity(it.toInt()) }, valueRange = 40f..100f, steps = 5)
    }
}

@Composable
private fun SizeChip(label: Int, value: GruPetSize, selected: GruPetSize, prefs: GruPreferences) {
    FilterChip(selected = value == selected, onClick = { prefs.setSize(value) }, label = { Text(stringResource(label)) })
}

@Composable
internal fun SectionTitle(text: Int) {
    Text(stringResource(text), style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.SemiBold)
}

private data class PetOption(val design: GruPet, val drawable: Int, val name: Int)
private fun petFor(design: GruPet): PetOption = PETS.first { it.design == design }
private val PETS = listOf(
    PetOption(GruPet.LUME, R.drawable.gru_pet_lume, R.string.gru__pet_lume),
    PetOption(GruPet.FAISCA, R.drawable.gru_pet_faisca, R.string.gru__pet_faisca),
    PetOption(GruPet.BIP, R.drawable.gru_pet_bip, R.string.gru__pet_bip),
    PetOption(GruPet.PINGO, R.drawable.gru_pet_pingo, R.string.gru__pet_pingo),
    PetOption(GruPet.PUDIM, R.drawable.gru_pet_pudim, R.string.gru__pet_pudim),
)

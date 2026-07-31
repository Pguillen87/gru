/*
 * Copyright (C) 2026 Gru Contributors
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 */

package dev.patrickgold.florisboard.gru

import android.Manifest
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Image
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
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
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Slider
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
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
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen
import androidx.core.view.WindowCompat
import dev.patrickgold.florisboard.R
import dev.patrickgold.florisboard.dictate.overlay.DictateAccessibilityService
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Visibility
import androidx.compose.material.icons.filled.VisibilityOff

class GruActivity : ComponentActivity() {
    private val prefs by lazy { GruPreferences.get(this) }
    private var permissionRefresh by mutableIntStateOf(0)

    override fun onCreate(savedInstanceState: Bundle?) {
        installSplashScreen()
        super.onCreate(savedInstanceState)
        WindowCompat.setDecorFitsSystemWindows(window, false)
        installContent()
    }

    override fun onResume() {
        super.onResume()
        permissionRefresh++
    }

    private fun installContent() = setContent {
        GruTheme {
            Surface(color = MaterialTheme.colorScheme.background) {
                GruScreen(permissionRefresh)
            }
        }
    }

    @OptIn(ExperimentalMaterial3Api::class)
    @Composable
    private fun GruScreen(permissionRefresh: Int) {
        Scaffold(
            topBar = { TopAppBar(title = { Text(stringResource(R.string.gru__app_name)) }) },
        ) { padding ->
            GruContent(
                permissionRefresh = permissionRefresh,
                modifier = Modifier.padding(padding),
            )
        }
    }

    @Composable
    private fun GruContent(permissionRefresh: Int, modifier: Modifier = Modifier) {
        val context = LocalContext.current
        val enabled by prefs.enabled.collectAsState()
        val design by prefs.pet.collectAsState()
        val size by prefs.size.collectAsState()
        val opacity by prefs.opacity.collectAsState()
        val accessibilityReady = remember(permissionRefresh) { isGruAccessibilityEnabled(context) }
        val microphoneReady = remember(permissionRefresh) { hasPermission(context, Manifest.permission.RECORD_AUDIO) }
        val notificationsReady = remember(permissionRefresh) { notificationsAllowed(context) }

        Column(
            modifier = modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .navigationBarsPadding()
                .padding(horizontal = 20.dp, vertical = 12.dp),
            verticalArrangement = Arrangement.spacedBy(24.dp),
        ) {
            PetPreview(design, opacity)
            MasterToggle(enabled, prefs::setEnabled)
            PetPicker(design, prefs::setPet)
            AppearanceControls(size, opacity)
            TranscriptionSection()
            SetupSection(accessibilityReady, microphoneReady, notificationsReady)
            if (accessibilityReady && microphoneReady) {
                Text(
                    text = stringResource(R.string.gru__ready_message),
                    style = MaterialTheme.typography.bodyLarge,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Spacer(Modifier.height(8.dp))
        }
    }

    @Composable
    private fun PetPreview(design: GruPet, opacity: Int) {
        val pet = petFor(design)
        Column(
            modifier = Modifier.fillMaxWidth(),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Image(
                painter = painterResource(pet.drawable),
                contentDescription = stringResource(R.string.gru__preview_description, stringResource(pet.name)),
                contentScale = ContentScale.Fit,
                modifier = Modifier.size(132.dp).alpha(opacity.coerceIn(40, 100) / 100f),
            )
            Text(
                text = stringResource(R.string.gru__tagline),
                style = MaterialTheme.typography.headlineSmall,
                fontWeight = FontWeight.SemiBold,
            )
        }
    }

    @Composable
    private fun MasterToggle(enabled: Boolean, onChange: (Boolean) -> Unit) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(Modifier.weight(1f).padding(end = 16.dp)) {
                Text(stringResource(R.string.gru__pet_enabled), style = MaterialTheme.typography.titleMedium)
                Text(
                    stringResource(R.string.gru__pet_enabled_summary),
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Switch(checked = enabled, onCheckedChange = onChange)
        }
    }

    @Composable
    private fun PetPicker(selected: GruPet, onSelect: (GruPet) -> Unit) {
        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            SectionTitle(R.string.gru__choose_pet)
            pets.chunked(PET_PICKER_COLUMNS).forEach { rowPets ->
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    rowPets.forEach { pet ->
                        PetChoice(pet, selected == pet.design, Modifier.weight(1f)) { onSelect(pet.design) }
                    }
                    repeat(PET_PICKER_COLUMNS - rowPets.size) {
                        Spacer(Modifier.weight(1f))
                    }
                }
            }
        }
    }

    @Composable
    private fun PetChoice(pet: PetOption, isSelected: Boolean, modifier: Modifier, onClick: () -> Unit) {
        val borderColor = if (isSelected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.outlineVariant
        Column(
            modifier = modifier
                .semantics { selected = isSelected; role = Role.RadioButton }
                .border(if (isSelected) 2.dp else 1.dp, borderColor, RoundedCornerShape(8.dp))
                .clickable(onClick = onClick)
                .padding(vertical = 8.dp, horizontal = 4.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Image(painterResource(pet.drawable), null, modifier = Modifier.size(52.dp))
            Text(stringResource(pet.name), style = MaterialTheme.typography.labelMedium, maxLines = 1)
        }
    }

    @Composable
    private fun AppearanceControls(size: GruPetSize, opacity: Int) {
        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            SectionTitle(R.string.gru__appearance)
            Text(stringResource(R.string.gru__size), style = MaterialTheme.typography.bodyLarge)
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                SizeChip(R.string.gru__size_small, GruPetSize.SMALL, size)
                SizeChip(R.string.gru__size_medium, GruPetSize.MEDIUM, size)
                SizeChip(R.string.gru__size_large, GruPetSize.LARGE, size)
            }
            Text(stringResource(R.string.gru__opacity, opacity), style = MaterialTheme.typography.bodyLarge)
            Slider(
                value = opacity.toFloat(),
                onValueChange = { value -> prefs.setOpacity(value.toInt()) },
                valueRange = 40f..100f,
                steps = 5,
            )
        }
    }

    @Composable
    private fun SizeChip(label: Int, value: GruPetSize, selected: GruPetSize) {
        FilterChip(
            selected = value == selected,
            onClick = { prefs.setSize(value) },
            label = { Text(stringResource(label)) },
        )
    }

    @Composable
    private fun TranscriptionSection() {
        var apiKey by remember { mutableStateOf(prefs.groqApiKey) }
        var showKey by remember { mutableStateOf(false) }
        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            SectionTitle(R.string.gru__transcription_title)
            Text(
                stringResource(R.string.gru__provider_name),
                style = MaterialTheme.typography.bodyLarge,
                fontWeight = FontWeight.Medium,
            )
            OutlinedTextField(
                value = apiKey,
                onValueChange = { value ->
                    apiKey = value
                    prefs.groqApiKey = value
                },
                modifier = Modifier.fillMaxWidth(),
                label = { Text(stringResource(R.string.gru__api_key_label)) },
                supportingText = { Text(stringResource(R.string.gru__api_key_summary)) },
                singleLine = true,
                visualTransformation = if (showKey) VisualTransformation.None else PasswordVisualTransformation(),
                trailingIcon = {
                    IconButton(onClick = { showKey = !showKey }) {
                        Icon(
                            imageVector = if (showKey) Icons.Default.VisibilityOff else Icons.Default.Visibility,
                            contentDescription = stringResource(
                                if (showKey) R.string.gru__api_key_hide else R.string.gru__api_key_show,
                            ),
                        )
                    }
                },
            )
        }
    }

    @Composable
    private fun SetupSection(accessibilityReady: Boolean, microphoneReady: Boolean, notificationsReady: Boolean) {
        val context = LocalContext.current
        var showDisclosure by remember { mutableStateOf(false) }
        val micLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { permissionRefresh++ }
        val notificationLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { permissionRefresh++ }
        Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
            SectionTitle(if (accessibilityReady && microphoneReady) R.string.gru__setup_title else R.string.gru__setup_pending)
            PermissionRow(R.string.gru__accessibility_title, R.string.gru__accessibility_summary, accessibilityReady) { showDisclosure = true }
            HorizontalDivider()
            PermissionRow(R.string.gru__microphone_title, R.string.gru__microphone_summary, microphoneReady) {
                micLauncher.launch(Manifest.permission.RECORD_AUDIO)
            }
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                HorizontalDivider()
                PermissionRow(R.string.gru__notifications_title, R.string.gru__notifications_summary, notificationsReady) {
                    notificationLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
                }
            }
        }
        if (showDisclosure) AccessibilityDisclosure(
            onDismiss = { showDisclosure = false },
            onConfirm = {
                showDisclosure = false
                context.startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
            },
        )
    }

    @Composable
    private fun PermissionRow(title: Int, summary: Int, granted: Boolean, action: () -> Unit) {
        Column(
            modifier = Modifier.fillMaxWidth().padding(vertical = 12.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(stringResource(title), style = MaterialTheme.typography.titleSmall)
                Text(
                    stringResource(if (granted) R.string.gru__granted else R.string.gru__pending),
                    color = if (granted) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.error,
                    fontWeight = FontWeight.SemiBold,
                )
            }
            Text(stringResource(summary), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            if (!granted) Button(onClick = action, modifier = Modifier.fillMaxWidth()) { Text(permissionAction(title)) }
        }
    }

    @Composable
    private fun permissionAction(title: Int): String = when (title) {
        R.string.gru__accessibility_title -> stringResource(R.string.gru__accessibility_action)
        R.string.gru__microphone_title -> stringResource(R.string.gru__microphone_action)
        else -> stringResource(R.string.gru__notifications_action)
    }

    @Composable
    private fun AccessibilityDisclosure(onDismiss: () -> Unit, onConfirm: () -> Unit) {
        AlertDialog(
            onDismissRequest = onDismiss,
            title = { Text(stringResource(R.string.gru__accessibility_title)) },
            text = { Text(stringResource(R.string.gru__accessibility_summary)) },
            confirmButton = { TextButton(onClick = onConfirm) { Text(stringResource(R.string.gru__accessibility_action)) } },
            dismissButton = { TextButton(onClick = onDismiss) { Text(stringResource(android.R.string.cancel)) } },
        )
    }

    @Composable
    private fun SectionTitle(text: Int) {
        Text(stringResource(text), style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.SemiBold)
    }

    private fun isGruAccessibilityEnabled(context: Context): Boolean {
        val expected = ComponentName(context, DictateAccessibilityService::class.java)
        val enabled = Settings.Secure.getString(
            context.contentResolver,
            Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES,
        ).orEmpty()
        return enabled.split(':').any { ComponentName.unflattenFromString(it) == expected }
    }

    private fun hasPermission(context: Context, permission: String): Boolean =
        ContextCompat.checkSelfPermission(context, permission) == PackageManager.PERMISSION_GRANTED

    private fun notificationsAllowed(context: Context): Boolean =
        Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU || hasPermission(context, Manifest.permission.POST_NOTIFICATIONS)

    private data class PetOption(val design: GruPet, val drawable: Int, val name: Int)

    private fun petFor(design: GruPet): PetOption = pets.first { it.design == design }

    private companion object {
        val pets = listOf(
            PetOption(GruPet.LUME, R.drawable.gru_pet_lume, R.string.gru__pet_lume),
            PetOption(GruPet.FAISCA, R.drawable.gru_pet_faisca, R.string.gru__pet_faisca),
            PetOption(GruPet.BIP, R.drawable.gru_pet_bip, R.string.gru__pet_bip),
            PetOption(GruPet.PINGO, R.drawable.gru_pet_pingo, R.string.gru__pet_pingo),
            PetOption(GruPet.PUDIM, R.drawable.gru_pet_pudim, R.string.gru__pet_pudim),
        )

        const val PET_PICKER_COLUMNS = 3
    }
}

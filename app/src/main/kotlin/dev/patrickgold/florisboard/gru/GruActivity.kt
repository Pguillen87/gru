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
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Slider
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
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
import androidx.core.content.ContextCompat
import androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen
import androidx.core.view.WindowCompat
import androidx.lifecycle.lifecycleScope
import dev.patrickgold.florisboard.R
import dev.patrickgold.florisboard.app.AppTheme
import dev.patrickgold.florisboard.app.FlorisPreferenceStore
import dev.patrickgold.florisboard.app.apptheme.FlorisAppTheme
import dev.patrickgold.florisboard.appContext
import dev.patrickgold.florisboard.dictate.DictateFloatingButtonDesign
import dev.patrickgold.florisboard.dictate.DictateFloatingButtonSize
import dev.patrickgold.florisboard.dictate.overlay.DictateAccessibilityService
import dev.patrickgold.jetpref.datastore.model.collectAsState
import java.util.concurrent.atomic.AtomicBoolean
import kotlinx.coroutines.launch
import org.florisboard.lib.kotlin.collectIn

class GruActivity : ComponentActivity() {
    private val prefs by FlorisPreferenceStore
    private val appContext by appContext()
    private var permissionRefresh by mutableIntStateOf(0)

    override fun onCreate(savedInstanceState: Bundle?) {
        installSplashScreen().setKeepOnScreenCondition { !appContext.preferenceStoreLoaded.value }
        super.onCreate(savedInstanceState)
        WindowCompat.setDecorFitsSystemWindows(window, false)
        val contentInstalled = AtomicBoolean(false)
        appContext.preferenceStoreLoaded.collectIn(lifecycleScope) { loaded ->
            if (loaded && !contentInstalled.getAndSet(true)) installContent()
        }
    }

    override fun onResume() {
        super.onResume()
        permissionRefresh++
    }

    private fun installContent() = setContent {
        FlorisAppTheme(theme = AppTheme.AUTO) {
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
        val scope = rememberCoroutineScope()
        val enabled by prefs.dictate.floatingButtonEnabled.collectAsState()
        val design by prefs.dictate.floatingButtonDesign.collectAsState()
        val size by prefs.dictate.floatingButtonSize.collectAsState()
        val opacity by prefs.dictate.floatingButtonOpacity.collectAsState()
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
            MasterToggle(enabled) { value -> scope.launch { prefs.dictate.floatingButtonEnabled.set(value) } }
            PetPicker(design) { value -> scope.launch { prefs.dictate.floatingButtonDesign.set(value) } }
            AppearanceControls(size, opacity)
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
    private fun PetPreview(design: DictateFloatingButtonDesign, opacity: Int) {
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
    private fun PetPicker(selected: DictateFloatingButtonDesign, onSelect: (DictateFloatingButtonDesign) -> Unit) {
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
    private fun AppearanceControls(size: DictateFloatingButtonSize, opacity: Int) {
        val scope = rememberCoroutineScope()
        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            SectionTitle(R.string.gru__appearance)
            Text(stringResource(R.string.gru__size), style = MaterialTheme.typography.bodyLarge)
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                SizeChip(R.string.gru__size_small, DictateFloatingButtonSize.SMALL, size)
                SizeChip(R.string.gru__size_medium, DictateFloatingButtonSize.MEDIUM, size)
                SizeChip(R.string.gru__size_large, DictateFloatingButtonSize.LARGE, size)
            }
            Text(stringResource(R.string.gru__opacity, opacity), style = MaterialTheme.typography.bodyLarge)
            Slider(
                value = opacity.toFloat(),
                onValueChange = { value ->
                    scope.launch { prefs.dictate.floatingButtonOpacity.set(value.toInt().coerceIn(40, 100)) }
                },
                valueRange = 40f..100f,
                steps = 5,
            )
        }
    }

    @Composable
    private fun SizeChip(label: Int, value: DictateFloatingButtonSize, selected: DictateFloatingButtonSize) {
        val scope = rememberCoroutineScope()
        FilterChip(
            selected = value == selected,
            onClick = { scope.launch { prefs.dictate.floatingButtonSize.set(value) } },
            label = { Text(stringResource(label)) },
        )
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

    private data class PetOption(val design: DictateFloatingButtonDesign, val drawable: Int, val name: Int)

    private fun petFor(design: DictateFloatingButtonDesign): PetOption = pets.first { it.design == design }

    private companion object {
        val pets = listOf(
            PetOption(DictateFloatingButtonDesign.PILL, R.drawable.gru_pet_lume, R.string.gru__pet_lume),
            PetOption(DictateFloatingButtonDesign.RING, R.drawable.gru_pet_faisca, R.string.gru__pet_faisca),
            PetOption(DictateFloatingButtonDesign.ORB, R.drawable.gru_pet_bip, R.string.gru__pet_bip),
            PetOption(DictateFloatingButtonDesign.CLOUD, R.drawable.gru_pet_pingo, R.string.gru__pet_pingo),
            PetOption(DictateFloatingButtonDesign.PUDIM, R.drawable.gru_pet_pudim, R.string.gru__pet_pudim),
        )

        const val PET_PICKER_COLUMNS = 3
    }
}

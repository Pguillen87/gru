/*
 * Copyright (C) 2026 Gru Contributors
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 */

package com.pguillen.gru

import android.Manifest
import android.content.ComponentName
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.Image
import androidx.compose.foundation.clickable
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AddCircle
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.GraphicEq
import androidx.compose.material.icons.filled.Pets
import androidx.compose.material.icons.filled.PowerSettingsNew
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.Alignment
import androidx.compose.ui.draw.clip
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen
import androidx.core.view.WindowCompat
import com.pguillen.gru.overlay.GruAccessibilityService
import com.pguillen.gru.local.WhisperModelManager
import com.pguillen.gru.local.WhisperModelState

class GruActivity : ComponentActivity() {
    private val prefs by lazy { GruPreferences.get(this) }
    private var permissionRefresh by mutableIntStateOf(0)

    override fun onCreate(savedInstanceState: Bundle?) {
        installSplashScreen()
        super.onCreate(savedInstanceState)
        WindowCompat.setDecorFitsSystemWindows(window, false)
        setContent {
            GruTheme {
                Surface(color = MaterialTheme.colorScheme.background) {
                    GruApp(permissionRefresh, prefs) { permissionRefresh++ }
                }
            }
        }
    }

    override fun onResume() {
        super.onResume()
        permissionRefresh++
    }
}

internal enum class GruDestination(val label: Int) {
    PERMISSIONS(R.string.gru__nav_permissions),
    VOICE(R.string.gru__nav_voice),
    CONTROL(R.string.gru__nav_control),
    MASCOTS(R.string.gru__nav_mascots),
    CREATE_MASCOT(R.string.gru__nav_create_mascot),
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun GruApp(permissionRefresh: Int, prefs: GruPreferences, onPermissionChanged: () -> Unit) {
    val context = LocalContext.current
    val modelManager = remember { WhisperModelManager.get(context) }
    val engine by prefs.engine.collectAsState()
    val modelState by modelManager.state.collectAsState()
    var destination by remember { mutableIntStateOf(GruDestination.PERMISSIONS.ordinal) }
    LaunchedEffect(engine, modelState) {
        if (modelState !is WhisperModelState.Preparing && modelState !is WhisperModelState.Verifying) {
            prefs.reconcileEngine(modelState is WhisperModelState.Installed)
        }
    }
    Scaffold(
        topBar = { TopAppBar(title = { GruBrandTitle() }) },
        bottomBar = {
            if (engine != null) {
                GruBottomNavigation(
                    selected = GruDestination.entries[destination],
                    onSelect = { destination = it.ordinal },
                )
            }
        },
    ) { padding ->
        if (engine == null) {
            GruTranscriptionScreen(
                prefs = prefs,
                firstUse = true,
                onConfigured = { destination = GruDestination.PERMISSIONS.ordinal },
                modifier = Modifier.fillMaxSize().padding(padding),
            )
        } else when (GruDestination.entries[destination]) {
            GruDestination.PERMISSIONS -> GruGeneralScreen(
                prefs = prefs,
                permissionRefresh = permissionRefresh,
                onPermissionChanged = onPermissionChanged,
                modifier = Modifier.fillMaxSize().padding(padding),
            )
            GruDestination.VOICE -> GruTranscriptionScreen(
                prefs = prefs,
                modifier = Modifier.fillMaxSize().padding(padding),
            )
            GruDestination.CONTROL -> GruControlScreen(
                prefs = prefs,
                permissionRefresh = permissionRefresh,
                onResolvePermissions = { destination = GruDestination.PERMISSIONS.ordinal },
                onResolveVoice = { destination = GruDestination.VOICE.ordinal },
                modifier = Modifier.fillMaxSize().padding(padding),
            )
            GruDestination.MASCOTS -> GruMascotScreen(
                prefs = prefs,
                permissionRefresh = permissionRefresh,
                modifier = Modifier.fillMaxSize().padding(padding),
            )
            GruDestination.CREATE_MASCOT -> GruMascotScreen(
                prefs = prefs,
                permissionRefresh = permissionRefresh,
                focus = MascotFocus.CREATE,
                modifier = Modifier.fillMaxSize().padding(padding),
            )
        }
    }
}

@Composable
private fun GruBottomNavigation(selected: GruDestination, onSelect: (GruDestination) -> Unit) {
    val items = listOf(
        GruDestination.PERMISSIONS to Icons.Default.CheckCircle,
        GruDestination.VOICE to Icons.Default.GraphicEq,
        GruDestination.CONTROL to Icons.Default.PowerSettingsNew,
        GruDestination.MASCOTS to Icons.Default.Pets,
        GruDestination.CREATE_MASCOT to Icons.Default.AddCircle,
    )
    NavigationBar(modifier = Modifier.navigationBarsPadding()) {
        items.forEach { (destination, icon) ->
            val isCentral = destination == GruDestination.CONTROL
            if (isCentral) {
                Box(
                    modifier = Modifier.weight(1f).fillMaxHeight(),
                    contentAlignment = Alignment.Center,
                ) {
                    Column(
                        modifier = Modifier
                            .clip(MaterialTheme.shapes.large)
                            .semantics {
                                this.selected = selected == destination
                                role = Role.Tab
                            }
                            .clickable { onSelect(destination) }
                            .padding(horizontal = 8.dp, vertical = 2.dp),
                        horizontalAlignment = Alignment.CenterHorizontally,
                    ) {
                        Icon(icon, contentDescription = null, modifier = Modifier.size(36.dp))
                        Text(stringResource(destination.label), maxLines = 2, style = MaterialTheme.typography.labelSmall)
                    }
                }
            } else {
                NavigationBarItem(
                    selected = selected == destination,
                    onClick = { onSelect(destination) },
                    icon = { Icon(icon, contentDescription = null) },
                    label = { Text(stringResource(destination.label), maxLines = 2) },
                    modifier = Modifier.semantics { role = Role.Tab },
                )
            }
        }
    }
}

@Composable
private fun GruBrandTitle() {
    Row(
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Image(
            painter = painterResource(R.drawable.gru_brand_master),
            contentDescription = stringResource(R.string.gru__brand_logo),
            contentScale = androidx.compose.ui.layout.ContentScale.Fit,
            modifier = Modifier.size(48.dp),
        )
        Text(stringResource(R.string.gru__app_name))
    }
}

internal fun isGruAccessibilityEnabled(context: Context): Boolean {
    val expected = ComponentName(context, GruAccessibilityService::class.java)
    val enabled = Settings.Secure.getString(
        context.contentResolver,
        Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES,
    ).orEmpty()
    return enabled.split(':').any { ComponentName.unflattenFromString(it) == expected }
}

internal fun hasPermission(context: Context, permission: String): Boolean =
    ContextCompat.checkSelfPermission(context, permission) == PackageManager.PERMISSION_GRANTED

internal fun notificationsAllowed(context: Context): Boolean =
    Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU || hasPermission(context, Manifest.permission.POST_NOTIFICATIONS)

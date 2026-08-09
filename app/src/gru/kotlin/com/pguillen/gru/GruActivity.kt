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
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.clickable
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.GraphicEq
import androidx.compose.material.icons.filled.Pets
import androidx.compose.material.icons.filled.PowerSettingsNew
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
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
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
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
                Surface(
                    modifier = Modifier.fillMaxSize(),
                    color = MaterialTheme.colorScheme.background,
                ) {
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
    PERCH(R.string.gru__nav_perch),
}

@Composable
private fun GruApp(permissionRefresh: Int, prefs: GruPreferences, onPermissionChanged: () -> Unit) {
    val context = LocalContext.current
    val modelManager = remember { WhisperModelManager.get(context) }
    val engine by prefs.engine.collectAsState()
    val onboardingCompleted by prefs.onboardingCompleted.collectAsState()
    val modelState by modelManager.state.collectAsState()
    var destination by remember { mutableIntStateOf(GruDestination.PERMISSIONS.ordinal) }
    LaunchedEffect(engine, modelState) {
        if (modelState !is WhisperModelState.Preparing && modelState !is WhisperModelState.Verifying) {
            prefs.reconcileEngine(modelState is WhisperModelState.Installed)
        }
    }
    Scaffold(
        bottomBar = {
            if (shouldShowMainNavigation(onboardingCompleted)) {
                GruBottomNavigation(
                    selected = GruDestination.entries[destination],
                    onSelect = { destination = it.ordinal },
                )
            }
        },
    ) { padding ->
        if (!onboardingCompleted) {
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
                modifier = Modifier.fillMaxSize().padding(padding),
            )
            GruDestination.PERCH -> GruPerchScreen(
                prefs = prefs,
                modifier = Modifier.fillMaxSize().padding(padding),
            )
        }
    }
}

internal fun shouldShowMainNavigation(onboardingCompleted: Boolean): Boolean = onboardingCompleted

@Composable
private fun GruBottomNavigation(selected: GruDestination, onSelect: (GruDestination) -> Unit) {
    val largeText = LocalDensity.current.fontScale >= 1.5f
    val items = listOf(
        GruDestination.PERMISSIONS to Icons.Default.CheckCircle,
        GruDestination.VOICE to Icons.Default.GraphicEq,
        GruDestination.CONTROL to Icons.Default.PowerSettingsNew,
        GruDestination.MASCOTS to Icons.Default.Pets,
        GruDestination.PERCH to Icons.Default.Home,
    )
    Box(
        Modifier.fillMaxWidth().navigationBarsPadding().padding(horizontal = 10.dp, vertical = 8.dp),
        contentAlignment = Alignment.BottomCenter,
    ) {
        Surface(
            color = MaterialTheme.colorScheme.surface.copy(alpha = 0.98f),
            shape = RoundedCornerShape(28.dp),
            border = androidx.compose.foundation.BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant),
            modifier = Modifier.fillMaxWidth()
                .heightIn(min = if (largeText) 104.dp else 72.dp)
                .shadow(18.dp, RoundedCornerShape(28.dp)),
        ) {
            Row(
                Modifier.fillMaxSize().padding(horizontal = 4.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                items.forEach { (destination, icon) ->
                    val active = selected == destination
                    val central = destination == GruDestination.CONTROL
                    val label = stringResource(destination.label)
                    Column(
                        modifier = Modifier
                            .weight(1f)
                            .clip(RoundedCornerShape(20.dp))
                            .semantics {
                                this.selected = active
                                role = Role.Tab
                            }
                            .clickable { onSelect(destination) }
                            .padding(vertical = 4.dp),
                        horizontalAlignment = Alignment.CenterHorizontally,
                    ) {
                        if (central) {
                            Surface(
                                shape = CircleShape,
                                color = MaterialTheme.colorScheme.surfaceVariant,
                                border = androidx.compose.foundation.BorderStroke(2.dp, GruColors.Cyan),
                                modifier = Modifier.size(48.dp).offset(y = (-6).dp),
                            ) {
                                Box(contentAlignment = Alignment.Center) {
                                    Icon(icon, contentDescription = null, tint = GruColors.Cyan, modifier = Modifier.size(26.dp))
                                }
                            }
                        } else {
                            Icon(
                                icon,
                                contentDescription = null,
                                tint = if (active) GruColors.Cyan else MaterialTheme.colorScheme.onSurfaceVariant,
                                modifier = Modifier.size(22.dp),
                            )
                        }
                        Text(
                            label,
                            color = if (active) GruColors.Cyan else MaterialTheme.colorScheme.onSurfaceVariant,
                            style = MaterialTheme.typography.labelSmall,
                            maxLines = 2,
                            modifier = if (central) Modifier.offset(y = (-5).dp) else Modifier,
                        )
                    }
                }
            }
        }
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

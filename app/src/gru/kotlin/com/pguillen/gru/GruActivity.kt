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
import androidx.compose.foundation.Image
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.PrimaryTabRow
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Tab
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
    GENERAL(R.string.gru__general_tab),
    TRANSCRIPTION(R.string.gru__transcription_tab),
    MASCOT(R.string.gru__mascot_tab),
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun GruApp(permissionRefresh: Int, prefs: GruPreferences, onPermissionChanged: () -> Unit) {
    val context = LocalContext.current
    val modelManager = remember { WhisperModelManager.get(context) }
    val engine by prefs.engine.collectAsState()
    val modelState by modelManager.state.collectAsState()
    var destination by remember {
        mutableIntStateOf(GruDestination.GENERAL.ordinal)
    }
    LaunchedEffect(engine, modelState) {
        if (modelState !is WhisperModelState.Preparing && modelState !is WhisperModelState.Verifying) {
            prefs.reconcileEngine(modelState is WhisperModelState.Installed)
        }
    }
    Scaffold(topBar = {
        Column {
            TopAppBar(title = { GruBrandTitle() })
            if (engine != null) {
                PrimaryTabRow(selectedTabIndex = destination) {
                    GruDestination.entries.forEachIndexed { index, item ->
                        Tab(
                            selected = destination == index,
                            onClick = { destination = index },
                            text = { Text(stringResource(item.label)) },
                        )
                    }
                }
            }
        }
    }) { padding ->
        if (engine == null) {
            GruTranscriptionScreen(
                prefs = prefs,
                firstUse = true,
                onConfigured = { destination = GruDestination.GENERAL.ordinal },
                modifier = Modifier.fillMaxSize().padding(padding),
            )
        } else when (GruDestination.entries[destination]) {
            GruDestination.GENERAL -> GruGeneralScreen(
                prefs = prefs,
                permissionRefresh = permissionRefresh,
                onPermissionChanged = onPermissionChanged,
                modifier = Modifier.fillMaxSize().padding(padding),
            )
            GruDestination.TRANSCRIPTION -> GruTranscriptionScreen(
                prefs = prefs,
                modifier = Modifier.fillMaxSize().padding(padding),
            )
            GruDestination.MASCOT -> GruMascotScreen(
                prefs = prefs,
                permissionRefresh = permissionRefresh,
                modifier = Modifier.fillMaxSize().padding(padding),
            )
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
            painter = painterResource(R.drawable.gru_brand_gro),
            contentDescription = stringResource(R.string.gru__brand_logo),
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

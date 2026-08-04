package com.pguillen.gru

import android.Manifest
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import com.pguillen.gru.dictation.TranscriptionEngine
import com.pguillen.gru.local.WhisperModelManager
import com.pguillen.gru.local.WhisperModelState
import com.pguillen.gru.overlay.GruOverlayHealth

@Composable
internal fun GruControlScreen(
    prefs: GruPreferences,
    permissionRefresh: Int,
    onResolvePermissions: () -> Unit,
    onResolveVoice: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val context = LocalContext.current
    val enabled by prefs.enabled.collectAsState()
    val engine by prefs.engine.collectAsState()
    val key by prefs.groqApiKeyState.collectAsState()
    val modelState by WhisperModelManager.get(context).state.collectAsState()
    val health by GruOverlayHealth.state.collectAsState()
    val accessibility = remember(permissionRefresh) { isGruAccessibilityEnabled(context) }
    val microphone = remember(permissionRefresh) { hasPermission(context, Manifest.permission.RECORD_AUDIO) }
    val engineReady = when (engine) {
        TranscriptionEngine.ONLINE_GROQ -> key.isNotBlank()
        TranscriptionEngine.PRIVATE_LOCAL -> modelState is WhisperModelState.Installed
        null -> false
    }
    val ready = accessibility && microphone && engineReady && health.serviceConnected
    val blockingAction = when {
        !engineReady -> onResolveVoice
        !accessibility || !microphone || !health.serviceConnected -> onResolvePermissions
        else -> null
    }
    val stateText = when {
        enabled -> R.string.gru__control_on
        !ready -> R.string.gru__control_needs_setup
        else -> R.string.gru__control_off
    }
    val stateDescription = stringResource(stateText)

    Column(
        modifier = modifier.verticalScroll(rememberScrollState()).padding(24.dp),
        verticalArrangement = Arrangement.spacedBy(20.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(stringResource(R.string.gru__control_title), style = MaterialTheme.typography.headlineMedium)
        Image(
            painter = painterResource(R.drawable.gru_brand_master),
            contentDescription = stringResource(R.string.gru__control_mascot_description),
            contentScale = ContentScale.Fit,
            modifier = Modifier.size(220.dp),
        )
        Text(
            stringResource(stateText),
            style = MaterialTheme.typography.headlineSmall,
            color = if (enabled) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurface,
            modifier = Modifier.semantics { contentDescription = stateDescription },
        )
        if (blockingAction != null) {
            Text(
                stringResource(R.string.gru__control_blocked_summary),
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            OutlinedButton(onClick = blockingAction, modifier = Modifier.fillMaxWidth()) {
                Text(stringResource(R.string.gru__resolve_now))
            }
        } else {
            Button(
                onClick = { prefs.setEnabled(!enabled) },
                modifier = Modifier.fillMaxWidth().padding(horizontal = 8.dp),
            ) {
                Text(stringResource(if (enabled) R.string.gru__turn_off else R.string.gru__turn_on))
            }
            Text(
                stringResource(R.string.gru__control_reversible),
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

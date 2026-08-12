package com.pguillen.gru

import android.Manifest
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.border
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.Icon
import androidx.compose.material3.Surface
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.PowerSettingsNew
import androidx.compose.material.icons.filled.Visibility
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
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.role
import androidx.compose.ui.unit.dp
import com.pguillen.gru.dictation.TranscriptionEngine
import com.pguillen.gru.local.WhisperModelManager
import com.pguillen.gru.local.WhisperModelState
import com.pguillen.gru.overlay.GruOverlayHealth
import com.pguillen.gru.overlay.ConversationSuppressionSession

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
    val suppression by ConversationSuppressionSession.state.collectAsState()
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
        !ready -> R.string.gru__control_needs_setup
        enabled -> R.string.gru__control_on
        else -> R.string.gru__control_off
    }
    val stateDescription = stringResource(stateText)

    Column(
        modifier = modifier.verticalScroll(rememberScrollState()).padding(horizontal = 20.dp, vertical = 8.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        GruBrandBar()
        Image(
            painter = painterResource(R.drawable.gru_brand_master),
            contentDescription = stringResource(R.string.gru__control_mascot_description),
            contentScale = ContentScale.Fit,
            modifier = Modifier.size(232.dp),
        )
        Text(
            stringResource(stateText).uppercase(),
            style = MaterialTheme.typography.headlineSmall,
            color = when {
                !ready -> GruColors.Gold
                enabled -> GruColors.Success
                else -> GruColors.Danger
            },
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
            Surface(
                onClick = { prefs.setEnabled(!enabled) },
                shape = CircleShape,
                color = (if (enabled) GruColors.Success else GruColors.Danger).copy(alpha = 0.09f),
                border = androidx.compose.foundation.BorderStroke(2.dp, if (enabled) GruColors.Success else GruColors.Danger),
                modifier = Modifier.size(132.dp).semantics { role = Role.Button },
            ) {
                Box(contentAlignment = Alignment.Center) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Icon(
                            Icons.Default.PowerSettingsNew,
                            contentDescription = null,
                            tint = if (enabled) GruColors.Success else GruColors.Danger,
                            modifier = Modifier.size(40.dp),
                        )
                        Text(
                            stringResource(if (enabled) R.string.gru__turn_off else R.string.gru__turn_on).uppercase(),
                            color = if (enabled) GruColors.Success else GruColors.Danger,
                            style = MaterialTheme.typography.labelLarge,
                        )
                    }
                }
            }
            Text(
                stringResource(R.string.gru__control_reversible),
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        if (suppression.count > 0) {
            SuppressedConversationsCard(suppression.count) { ConversationSuppressionSession.clearAll() }
        }
    }
}

@Composable
internal fun SuppressedConversationsCard(count: Int, onClear: () -> Unit) {
    if (count <= 0) return
    Surface(
        shape = MaterialTheme.shapes.medium,
        color = MaterialTheme.colorScheme.surfaceVariant,
        modifier = Modifier.fillMaxWidth(),
    ) {
        Column(
            Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Icon(
                Icons.Default.Visibility,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.primary,
            )
            Text(
                stringResource(R.string.gru__suppressed_conversations_title),
                style = MaterialTheme.typography.titleMedium,
            )
            Text(
                pluralStringResource(R.plurals.gru__suppressed_conversations_summary, count, count),
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            OutlinedButton(onClick = onClear, modifier = Modifier.fillMaxWidth()) {
                Text(stringResource(R.string.gru__show_again))
            }
        }
    }
}

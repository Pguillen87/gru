package com.pguillen.gru

import android.content.ClipboardManager
import android.content.Context
import android.graphics.BitmapFactory
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLayoutDirection
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.LayoutDirection
import com.pguillen.gru.mascot.CustomMascotStore
import com.pguillen.gru.mascot.importing.HttpMascotAssetDownloader
import com.pguillen.gru.mascot.importing.MascotImportCoordinator
import com.pguillen.gru.mascot.importing.MascotImportState
import com.pguillen.gru.mascot.importing.MascotPackageInstaller
import com.pguillen.gru.mascot.importing.UnavailableMascotCodeResolver
import kotlinx.coroutines.launch

@Composable
internal fun GruPerchScreen(prefs: GruPreferences, modifier: Modifier = Modifier) {
    val context = LocalContext.current
    val coordinator = remember {
        val store = CustomMascotStore(context)
        MascotImportCoordinator(
            UnavailableMascotCodeResolver,
            MascotPackageInstaller(store, HttpMascotAssetDownloader()),
            store,
            HttpMascotAssetDownloader(),
        )
    }
    val state by coordinator.state.collectAsState()
    var code by remember { mutableStateOf("") }
    val scope = rememberCoroutineScope()

    Column(
        modifier.verticalScroll(rememberScrollState()).imePadding().navigationBarsPadding().padding(horizontal = 20.dp, vertical = 12.dp),
        verticalArrangement = Arrangement.spacedBy(20.dp),
    ) {
        GruBrandBar()
        Text(stringResource(R.string.gru__perch_title), style = MaterialTheme.typography.headlineMedium)
        Text(stringResource(R.string.gru__perch_summary), color = MaterialTheme.colorScheme.onSurfaceVariant)
        Image(
            painterResource(R.drawable.gru_brand_master),
            contentDescription = null,
            contentScale = ContentScale.Fit,
            modifier = Modifier.fillMaxWidth().size(180.dp),
        )
        Text(stringResource(R.string.gru__perch_invitation), style = MaterialTheme.typography.titleMedium)
        CompositionLocalProvider(LocalLayoutDirection provides LayoutDirection.Ltr) {
            OutlinedTextField(
                value = code,
                onValueChange = { code = it.take(48) },
                label = { Text(stringResource(R.string.gru__mascot_code)) },
                singleLine = false,
                modifier = Modifier.fillMaxWidth(),
            )
        }
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            OutlinedButton(onClick = { code = clipboardTextForPerch(context) }, modifier = Modifier.weight(1f)) {
                Text(stringResource(R.string.gru__paste_code))
            }
            Button(onClick = { scope.launch { coordinator.resolve(code) } }, modifier = Modifier.weight(1f)) {
                Text(stringResource(R.string.gru__search_code))
            }
        }
        PerchStateContent(state, coordinator, prefs)
    }
}

@Composable
private fun PerchStateContent(state: MascotImportState, coordinator: MascotImportCoordinator, prefs: GruPreferences) {
    val scope = rememberCoroutineScope()
    Column(Modifier.semantics { liveRegion = LiveRegionMode.Polite }, verticalArrangement = Arrangement.spacedBy(12.dp)) {
        when (state) {
            MascotImportState.Idle -> Unit
            MascotImportState.Resolving -> Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                CircularProgressIndicator(Modifier.size(24.dp)); Text(stringResource(R.string.gru__perch_searching))
            }
            MascotImportState.InvalidCode -> PerchError(R.string.gru__perch_invalid_code)
            MascotImportState.NotConfigured -> PerchNotice(R.string.gru__perch_not_ready)
            MascotImportState.NotFound -> PerchError(R.string.gru__perch_not_found)
            MascotImportState.AccessDenied -> PerchError(R.string.gru__perch_access_denied)
            MascotImportState.NetworkUnavailable -> PerchError(R.string.gru__perch_network_error)
            is MascotImportState.ResolveFailed, is MascotImportState.UnsupportedManifest -> PerchError(R.string.gru__perch_cannot_open)
            is MascotImportState.PreviewReady -> {
                remember(state.previewBytes) { decodePerchPreview(state.previewBytes)?.asImageBitmap() }?.let { preview ->
                    Image(preview, state.manifest.displayName, contentScale = ContentScale.Fit, modifier = Modifier.fillMaxWidth().size(220.dp))
                }
                Text(state.manifest.displayName, style = MaterialTheme.typography.headlineSmall)
                Text(stringResource(R.string.gru__perch_origin))
                PoseChecklist()
                Button(onClick = { scope.launch { coordinator.install() } }, modifier = Modifier.fillMaxWidth()) {
                    Text(stringResource(R.string.gru__download_mascot))
                }
                OutlinedButton(onClick = coordinator::reset, modifier = Modifier.fillMaxWidth()) { Text(stringResource(android.R.string.cancel)) }
            }
            is MascotImportState.Downloading -> {
                Text(stringResource(R.string.gru__perch_downloading, state.completed, state.total))
                LinearProgressIndicator(progress = { state.completed.toFloat() / state.total }, modifier = Modifier.fillMaxWidth())
            }
            is MascotImportState.Verifying -> ProgressMessage(R.string.gru__perch_verifying)
            is MascotImportState.Installing -> ProgressMessage(R.string.gru__perch_installing)
            is MascotImportState.Installed -> {
                Icon(Icons.Default.CheckCircle, null, tint = GruColors.Success)
                Text(stringResource(R.string.gru__perch_installed, state.manifest.displayName))
                Button(onClick = { prefs.selectCustomMascot(state.packageKey, state.manifest.mascotId) }, modifier = Modifier.fillMaxWidth()) {
                    Text(stringResource(R.string.gru__use_now))
                }
            }
            is MascotImportState.AlreadyInstalled -> {
                Text(stringResource(R.string.gru__perch_already_installed))
                Button(
                    onClick = { prefs.selectCustomMascot(state.manifest.packageKey(), state.manifest.mascotId) },
                    modifier = Modifier.fillMaxWidth(),
                ) { Text(stringResource(R.string.gru__use_now)) }
                OutlinedButton(onClick = coordinator::reset, modifier = Modifier.fillMaxWidth()) { Text(stringResource(R.string.gru__close)) }
            }
            is MascotImportState.DownloadFailed -> RecoverablePerchError(R.string.gru__perch_download_failed, coordinator)
            is MascotImportState.IntegrityFailed -> RecoverablePerchError(R.string.gru__perch_integrity_failed, coordinator)
            MascotImportState.InstallFailed -> RecoverablePerchError(R.string.gru__perch_install_failed, coordinator)
        }
    }
}

@Composable private fun PoseChecklist() {
    listOf(R.string.gru__pose_normal, R.string.gru__pose_listening, R.string.gru__pose_transcribing).forEach {
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
            Icon(Icons.Default.CheckCircle, null, tint = GruColors.Success); Text(stringResource(it))
        }
    }
}

@Composable private fun PerchError(message: Int) { Text(stringResource(message), color = MaterialTheme.colorScheme.error) }

@Composable private fun PerchNotice(message: Int) { Text(stringResource(message), color = MaterialTheme.colorScheme.onSurfaceVariant) }

@Composable private fun ProgressMessage(message: Int) {
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        CircularProgressIndicator(Modifier.size(24.dp))
        Text(stringResource(message), color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable private fun RecoverablePerchError(message: Int, coordinator: MascotImportCoordinator) {
    PerchError(message)
    OutlinedButton(onClick = coordinator::reset, modifier = Modifier.fillMaxWidth()) {
        Text(stringResource(R.string.gru__try_another_code))
    }
}

private fun clipboardTextForPerch(context: Context): String = context.getSystemService(ClipboardManager::class.java)
    ?.primaryClip?.getItemAt(0)?.coerceToText(context)?.toString().orEmpty().trim()

private fun decodePerchPreview(bytes: ByteArray) = BitmapFactory.Options().let { bounds ->
    bounds.inJustDecodeBounds = true
    BitmapFactory.decodeByteArray(bytes, 0, bytes.size, bounds)
    var sample = 1
    while (bounds.outWidth / sample > 1024 || bounds.outHeight / sample > 1024) sample *= 2
    BitmapFactory.decodeByteArray(bytes, 0, bytes.size, BitmapFactory.Options().apply { inSampleSize = sample })
}

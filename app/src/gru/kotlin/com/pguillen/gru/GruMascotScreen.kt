package com.pguillen.gru

import android.graphics.BitmapFactory
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.result.PickVisualMediaRequest
import androidx.compose.foundation.Image
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Slider
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.pguillen.gru.dictation.TranscriptionEngine
import com.pguillen.gru.local.WhisperModelManager
import com.pguillen.gru.local.WhisperModelState
import com.pguillen.gru.mascot.MascotSource

@Composable
internal fun GruMascotScreen(prefs: GruPreferences, permissionRefresh: Int, modifier: Modifier = Modifier) {
    val context = LocalContext.current
    val source by prefs.mascotSource.collectAsState()
    val enabled by prefs.enabled.collectAsState()
    val size by prefs.size.collectAsState()
    val opacity by prefs.opacity.collectAsState()
    val engine by prefs.engine.collectAsState()
    val key by prefs.groqApiKeyState.collectAsState()
    val modelState by WhisperModelManager.get(context).state.collectAsState()
    val ready = isGruAccessibilityEnabled(context) && hasPermission(context, android.Manifest.permission.RECORD_AUDIO) && when (engine) {
        TranscriptionEngine.ONLINE_GROQ -> key.isNotBlank()
        TranscriptionEngine.PRIVATE_LOCAL -> modelState is WhisperModelState.Installed
        null -> false
    }
    var photo by remember { mutableStateOf<Uri?>(null) }
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.PickVisualMedia()) { photo = it }
    Column(modifier.verticalScroll(rememberScrollState()).padding(20.dp), verticalArrangement = Arrangement.spacedBy(20.dp)) {
        Text(stringResource(R.string.gru__my_mascot), style = MaterialTheme.typography.headlineSmall)
        MascotPreview(source, opacity)
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.SpaceBetween) {
            Column(Modifier.weight(1f)) {
                Text(stringResource(R.string.gru__pet_enabled), style = MaterialTheme.typography.titleMedium)
                Text(stringResource(R.string.gru__pet_enabled_summary), style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Switch(enabled, prefs::setEnabled, enabled = ready)
        }
        Text(stringResource(R.string.gru__gru_mascots), style = MaterialTheme.typography.titleLarge)
        BuiltInPicker(source, prefs::setPet)
        Text(stringResource(R.string.gru__create_mascot), style = MaterialTheme.typography.titleLarge)
        Text(stringResource(R.string.gru__create_mascot_summary), color = MaterialTheme.colorScheme.onSurfaceVariant)
        if (photo == null) Button(onClick = { picker.launch(PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly)) }, modifier = Modifier.fillMaxWidth()) {
            Text(stringResource(R.string.gru__choose_photo))
        } else PhotoConfirmation(photo!!, onChange = { picker.launch(PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly)) }, onCancel = { photo = null })
        Text(stringResource(R.string.gru__appearance), style = MaterialTheme.typography.titleLarge)
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            GruPetSize.entries.forEach { option -> FilterChip(option == size, { prefs.setSize(option) }, { Text(stringResource(sizeLabel(option))) }) }
        }
        Text(stringResource(R.string.gru__opacity, opacity))
        Slider(opacity.toFloat(), { prefs.setOpacity(it.toInt()) }, valueRange = 40f..100f, steps = 5)
        if (source is MascotSource.Custom) {
            Text(stringResource(R.string.gru__poses), style = MaterialTheme.typography.titleLarge)
            Text(stringResource(R.string.gru__poses_summary), color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Spacer(Modifier.height(12.dp))
    }
}

@Composable private fun MascotPreview(source: MascotSource, opacity: Int) {
    val pet = (source as? MascotSource.BuiltIn)?.pet ?: GruPet.FAISCA
    val option = petOption(pet)
    Column(Modifier.fillMaxWidth(), horizontalAlignment = Alignment.CenterHorizontally) {
        Image(painterResource(option.drawable), stringResource(R.string.gru__preview_description, stringResource(option.name)), contentScale = ContentScale.Fit, modifier = Modifier.size(144.dp).alpha(opacity / 100f))
        Text(stringResource(if (source is MascotSource.Custom) R.string.gru__custom_mascot else option.name), style = MaterialTheme.typography.titleMedium)
    }
}

@Composable private fun BuiltInPicker(selected: MascotSource, select: (GruPet) -> Unit) {
    PET_OPTIONS.chunked(3).forEach { row -> Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        row.forEach { option -> Column(Modifier.weight(1f).border(1.dp, MaterialTheme.colorScheme.outlineVariant, RoundedCornerShape(10.dp)).clickable { select(option.pet) }.padding(8.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            Image(painterResource(option.drawable), null, modifier = Modifier.size(48.dp)); Text(stringResource(option.name))
        } }
    } }
}

@Composable private fun PhotoConfirmation(uri: Uri, onChange: () -> Unit, onCancel: () -> Unit) {
    val context = LocalContext.current
    val preview = remember(uri) { context.contentResolver.openInputStream(uri)?.use(BitmapFactory::decodeStream)?.asImageBitmap() }
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        preview?.let { Image(it, stringResource(R.string.gru__photo_preview), modifier = Modifier.size(160.dp), contentScale = ContentScale.Crop) }
        Text(stringResource(R.string.gru__photo_tip), color = MaterialTheme.colorScheme.onSurfaceVariant)
        Button(onClick = onChange, modifier = Modifier.fillMaxWidth()) { Text(stringResource(R.string.gru__choose_another_photo)) }
        Button(onClick = onCancel, modifier = Modifier.fillMaxWidth()) { Text(stringResource(android.R.string.cancel)) }
    }
}

private data class BuiltInOption(val pet: GruPet, val drawable: Int, val name: Int)
private fun petOption(pet: GruPet) = PET_OPTIONS.first { it.pet == pet }
private fun sizeLabel(size: GruPetSize) = when (size) { GruPetSize.SMALL -> R.string.gru__size_small; GruPetSize.MEDIUM -> R.string.gru__size_medium; GruPetSize.LARGE -> R.string.gru__size_large }
private val PET_OPTIONS = listOf(
    BuiltInOption(GruPet.LUME, R.drawable.gru_pet_lume, R.string.gru__pet_lume), BuiltInOption(GruPet.FAISCA, R.drawable.gru_pet_faisca, R.string.gru__pet_faisca), BuiltInOption(GruPet.BIP, R.drawable.gru_pet_bip, R.string.gru__pet_bip), BuiltInOption(GruPet.PINGO, R.drawable.gru_pet_pingo, R.string.gru__pet_pingo), BuiltInOption(GruPet.PUDIM, R.drawable.gru_pet_pudim, R.string.gru__pet_pudim),
)

package com.pguillen.gru

import android.graphics.BitmapFactory
import android.net.Uri
import android.content.Context
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.result.PickVisualMediaRequest
import androidx.compose.foundation.Image
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Box
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
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.CircularProgressIndicator
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
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.semantics.semantics
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.coroutines.Dispatchers
import com.pguillen.gru.dictation.TranscriptionEngine
import com.pguillen.gru.local.WhisperModelManager
import com.pguillen.gru.local.WhisperModelState
import com.pguillen.gru.mascot.MascotSource
import com.pguillen.gru.mascot.MascotApi
import com.pguillen.gru.mascot.FirebaseMascotAuthTokenProvider
import com.pguillen.gru.mascot.FirebaseMascotAppCheckTokenProvider
import com.pguillen.gru.mascot.MascotCreationState
import com.pguillen.gru.mascot.MascotFailureRecovery
import com.pguillen.gru.mascot.MascotRepository
import com.pguillen.gru.mascot.mascotErrorMessage
import com.pguillen.gru.mascot.toCreationState
import com.pguillen.gru.mascot.toMascotFailure
import com.pguillen.gru.mascot.MasterReference
import com.pguillen.gru.mascot.CustomMascotStore

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
    var creation by remember { mutableStateOf<MascotCreationState>(MascotCreationState.Idle) }
    var selectedMasterId by remember { mutableStateOf<String?>(null) }
    var masterPreviews by remember { mutableStateOf<Map<String, ImageBitmap>>(emptyMap()) }
    val scope = rememberCoroutineScope()
    val repository = remember { MascotRepository(MascotApi(FirebaseMascotAuthTokenProvider(), FirebaseMascotAppCheckTokenProvider()), prefs, CustomMascotStore(context)) }
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.PickVisualMedia()) {
        photo = it
        creation = if (it == null) MascotCreationState.Idle else MascotCreationState.PhotoSelected
    }
    LaunchedEffect(Unit) {
        runCatching { repository.resume() }.onSuccess { job ->
            if (job != null) {
                creation = job.toCreationState()
                if (job.state in setOf("FAILED", "CANCELED")) repository.clearPending()
            }
        }.onFailure { creation = it.toMascotFailure(prefs.pendingMascotJobId.value) }
    }
    val tracked = creation as? MascotCreationState.Tracking
    LaunchedEffect(tracked?.job?.jobId) {
        val jobId = tracked?.job?.jobId ?: return@LaunchedEffect
        var interval = 3_000L
        while (true) {
            delay(interval)
            val job = runCatching { repository.resume() }.getOrElse { error -> creation = error.toMascotFailure(jobId); return@LaunchedEffect }
                ?: return@LaunchedEffect
            creation = job.toCreationState()
            if (job.state in setOf("FAILED", "CANCELED")) repository.clearPending()
            if (job.state in setOf("COMPLETED", "FAILED", "CANCELED", "AWAITING_MASTER_APPROVAL")) return@LaunchedEffect
            interval = (interval * 2).coerceAtMost(15_000L)
        }
    }
    val awaiting = creation as? MascotCreationState.AwaitingMasterApproval
    LaunchedEffect(awaiting?.job?.jobId, awaiting?.job?.masters) {
        val masters = awaiting?.job?.masters ?: return@LaunchedEffect
        selectedMasterId = null
        masterPreviews = emptyMap()
        masterPreviews = masters.mapNotNull { reference ->
            runCatching {
                val bytes = repository.downloadMaster(reference)
                BitmapFactory.decodeByteArray(bytes, 0, bytes.size)?.asImageBitmap()
            }
                .getOrNull()?.let { reference.id to it }
        }.toMap()
    }
    val installing = creation as? MascotCreationState.InstallingMascot
    val installFailureMessage = stringResource(R.string.gru__mascot_install_failed)
    LaunchedEffect(installing?.jobId) {
        val jobId = installing?.jobId ?: return@LaunchedEffect
        creation = runCatching { repository.installCompletedMascot(jobId) }
            .fold(
                onSuccess = { installed ->
                    if (installed) MascotCreationState.Completed
                    else MascotCreationState.InstallFailed(
                        jobId,
                        installFailureMessage,
                    )
                },
                onFailure = {
                    MascotCreationState.InstallFailed(
                        jobId,
                        installFailureMessage,
                    )
                },
            )
    }
    Column(
        modifier.clipToBounds().verticalScroll(rememberScrollState()).padding(20.dp),
        verticalArrangement = Arrangement.spacedBy(20.dp),
    ) {
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
        MascotCreationPanel(
            photo = photo,
            state = creation,
            onPick = { picker.launch(PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly)) },
            onDiscardPhoto = { photo = null; creation = MascotCreationState.Idle; repository.clearPending() },
            onUsePhoto = { selected -> scope.launch {
                creation = MascotCreationState.Submitting
                runCatching { repository.create(context.readMascotPhoto(selected), context.contentResolver.getType(selected) ?: "image/jpeg") }
                    .onSuccess { creation = it.toCreationState() }
                    .onFailure { creation = it.toMascotFailure(prefs.pendingMascotJobId.value) }
            } },
            selectedMasterId = selectedMasterId,
            masterPreviews = masterPreviews,
            onSelectMaster = { selectedMasterId = it },
            onApprove = { masterId -> scope.launch {
                val awaiting = creation as? MascotCreationState.AwaitingMasterApproval ?: return@launch
                creation = MascotCreationState.Submitting
                runCatching { repository.approve(awaiting.job.jobId, masterId) }
                    .onSuccess { creation = it.toCreationState() }
                    .onFailure { creation = it.toMascotFailure(awaiting.job.jobId) }
            } },
            onRetryTracking = { scope.launch {
                val jobId = prefs.pendingMascotJobId.value
                runCatching { repository.resume() }
                    .onSuccess { job -> creation = job?.toCreationState() ?: MascotCreationState.Idle }
                    .onFailure { creation = it.toMascotFailure(jobId) }
            } },
            onRetryInstall = { jobId -> creation = MascotCreationState.InstallingMascot(jobId) },
            onCancelCreation = { scope.launch {
                val jobId = prefs.pendingMascotJobId.value ?: return@launch
                creation = MascotCreationState.Canceling
                runCatching { repository.cancel(jobId) }
                    .onSuccess { creation = it.toCreationState() }
                    .onFailure { creation = MascotCreationState.CancelPending(jobId) }
            } },
        )
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

@Composable private fun MascotCreationPanel(
    photo: Uri?, state: MascotCreationState, onPick: () -> Unit, onDiscardPhoto: () -> Unit,
    onUsePhoto: (Uri) -> Unit, selectedMasterId: String?, masterPreviews: Map<String, ImageBitmap>,
    onSelectMaster: (String) -> Unit, onApprove: (String) -> Unit, onRetryTracking: () -> Unit,
    onRetryInstall: (String) -> Unit,
    onCancelCreation: () -> Unit,
) {
    when (state) {
        MascotCreationState.Idle -> Button(onClick = onPick, modifier = Modifier.fillMaxWidth()) { Text(stringResource(R.string.gru__choose_photo)) }
        MascotCreationState.PhotoSelected -> Unit
        MascotCreationState.Submitting -> LoadingMessage(R.string.gru__mascot_submitting)
        is MascotCreationState.Tracking -> {
            LoadingMessage(if (state.job.state == "READY_FOR_GENERATION") R.string.gru__mascot_waiting_generation else R.string.gru__mascot_tracking)
            OutlinedButton(onClick = onCancelCreation, modifier = Modifier.fillMaxWidth()) { Text(stringResource(R.string.gru__cancel_creation)) }
        }
        is MascotCreationState.AwaitingMasterApproval -> MasterChoices(state.job.masters, masterPreviews, selectedMasterId, onSelectMaster, onApprove)
        is MascotCreationState.InstallingMascot -> LoadingMessage(R.string.gru__mascot_installing)
        MascotCreationState.Completed -> Text(
            stringResource(R.string.gru__mascot_install_complete),
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        is MascotCreationState.InstallFailed -> {
            Text(state.message, color = MaterialTheme.colorScheme.error)
            Button(onClick = { onRetryInstall(state.jobId) }, modifier = Modifier.fillMaxWidth()) {
                Text(stringResource(R.string.gru__try_again))
            }
        }
        is MascotCreationState.NetworkUnavailable -> {
            Text(stringResource(R.string.gru__mascot_network_paused), color = MaterialTheme.colorScheme.onSurfaceVariant)
            Button(onClick = onRetryTracking, modifier = Modifier.fillMaxWidth()) { Text(stringResource(R.string.gru__try_again)) }
            OutlinedButton(onClick = onCancelCreation, modifier = Modifier.fillMaxWidth()) { Text(stringResource(R.string.gru__cancel_creation)) }
        }
        MascotCreationState.SubmissionUncertain -> {
            Text(stringResource(R.string.gru__mascot_submission_uncertain), color = MaterialTheme.colorScheme.onSurfaceVariant)
            Button(onClick = onRetryTracking, modifier = Modifier.fillMaxWidth()) { Text(stringResource(R.string.gru__try_again)) }
        }
        is MascotCreationState.RemoteFailed -> {
            Text(state.message, color = MaterialTheme.colorScheme.error)
            if (state.recovery == MascotFailureRecovery.CHOOSE_PHOTO) {
                Button(onClick = onPick, modifier = Modifier.fillMaxWidth()) {
                    Text(stringResource(R.string.gru__try_another_photo))
                }
            } else {
                Button(onClick = onRetryTracking, modifier = Modifier.fillMaxWidth()) {
                    Text(stringResource(R.string.gru__try_again))
                }
            }
        }
        MascotCreationState.Canceling -> LoadingMessage(R.string.gru__canceling_creation)
        is MascotCreationState.CancelPending -> {
            Text(stringResource(R.string.gru__cancel_pending), color = MaterialTheme.colorScheme.onSurfaceVariant)
            Button(onClick = onRetryTracking, modifier = Modifier.fillMaxWidth()) { Text(stringResource(R.string.gru__try_again)) }
        }
        MascotCreationState.Canceled -> Button(onClick = onPick, modifier = Modifier.fillMaxWidth()) { Text(stringResource(R.string.gru__choose_photo)) }
    }
    if (photo != null && state is MascotCreationState.PhotoSelected) {
        PhotoConfirmation(photo, onUsePhoto, onPick, onDiscardPhoto)
    }
}

@Composable private fun MasterChoices(
    masters: List<MasterReference>, previews: Map<String, ImageBitmap>, selectedId: String?,
    onSelect: (String) -> Unit, onApprove: (String) -> Unit,
) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(stringResource(R.string.gru__choose_master), style = MaterialTheme.typography.titleMedium)
        if (masters.isEmpty()) Text(stringResource(R.string.gru__master_images_pending), color = MaterialTheme.colorScheme.onSurfaceVariant)
        masters.chunked(2).forEach { row -> Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            row.forEach { master ->
                val selected = selectedId == master.id
                val preview = previews[master.id]
                Column(
                    Modifier.weight(1f).semantics { this.selected = selected; role = Role.RadioButton }
                        .border(if (selected) 2.dp else 1.dp, if (selected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.outlineVariant, RoundedCornerShape(12.dp))
                        .clickable(enabled = preview != null) { onSelect(master.id) }.padding(8.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                ) {
                    if (preview != null) {
                        Image(
                            preview, stringResource(R.string.gru__master_preview_number, masters.indexOf(master) + 1),
                            modifier = Modifier.size(136.dp), contentScale = ContentScale.Fit,
                        )
                    } else {
                        Box(Modifier.size(136.dp), contentAlignment = Alignment.Center) {
                            Text(stringResource(R.string.gru__master_preview_unavailable), color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                }
            }
            if (row.size == 1) Spacer(Modifier.weight(1f))
        } }
        Button(onClick = { selectedId?.let(onApprove) }, enabled = selectedId != null, modifier = Modifier.fillMaxWidth()) {
            Text(stringResource(R.string.gru__choose_this_mascot))
        }
    }
}

@Composable private fun LoadingMessage(label: Int) {
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        CircularProgressIndicator(Modifier.size(24.dp)); Text(stringResource(label), color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable private fun PhotoConfirmation(uri: Uri, onUse: (Uri) -> Unit, onChange: () -> Unit, onCancel: () -> Unit) {
    val context = LocalContext.current
    val preview = remember(uri) { context.contentResolver.openInputStream(uri)?.use(BitmapFactory::decodeStream)?.asImageBitmap() }
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        preview?.let { Image(it, stringResource(R.string.gru__photo_preview), modifier = Modifier.size(160.dp), contentScale = ContentScale.Crop) }
        Text(stringResource(R.string.gru__photo_tip), color = MaterialTheme.colorScheme.onSurfaceVariant)
        Button(onClick = { onUse(uri) }, modifier = Modifier.fillMaxWidth()) { Text(stringResource(R.string.gru__use_this_photo)) }
        Button(onClick = onChange, modifier = Modifier.fillMaxWidth()) { Text(stringResource(R.string.gru__choose_another_photo)) }
        Button(onClick = onCancel, modifier = Modifier.fillMaxWidth()) { Text(stringResource(android.R.string.cancel)) }
    }
}

private suspend fun Context.readMascotPhoto(uri: Uri): ByteArray = withContext(Dispatchers.IO) {
    contentResolver.openInputStream(uri)?.use { input -> input.readBytes().also { require(it.size in 1..10_000_000) } }
        ?: throw IllegalArgumentException("Selected photo cannot be read.")
}

private data class BuiltInOption(val pet: GruPet, val drawable: Int, val name: Int)
private fun petOption(pet: GruPet) = PET_OPTIONS.first { it.pet == pet }
private fun sizeLabel(size: GruPetSize) = when (size) { GruPetSize.SMALL -> R.string.gru__size_small; GruPetSize.MEDIUM -> R.string.gru__size_medium; GruPetSize.LARGE -> R.string.gru__size_large }
private val PET_OPTIONS = listOf(
    BuiltInOption(GruPet.LUME, R.drawable.gru_pet_lume, R.string.gru__pet_lume), BuiltInOption(GruPet.FAISCA, R.drawable.gru_pet_faisca, R.string.gru__pet_faisca), BuiltInOption(GruPet.BIP, R.drawable.gru_pet_bip, R.string.gru__pet_bip), BuiltInOption(GruPet.PINGO, R.drawable.gru_pet_pingo, R.string.gru__pet_pingo), BuiltInOption(GruPet.PUDIM, R.drawable.gru_pet_pudim, R.string.gru__pet_pudim),
)

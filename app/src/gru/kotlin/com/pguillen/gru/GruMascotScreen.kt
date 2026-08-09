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
import androidx.compose.ui.draw.clip
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Slider
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Edit
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
import com.pguillen.gru.mascot.CustomMascotEntry
import com.pguillen.gru.mascot.MascotTelemetry
import com.pguillen.gru.mascot.prepareMascotPhoto
import com.pguillen.gru.mascot.normalizeDisplayName
import com.pguillen.gru.mascot.MascotPoseChoices
import com.pguillen.gru.mascot.PreparedMascotAssets

internal enum class MascotFocus { LIBRARY, CREATE }

@Composable
internal fun GruMascotScreen(
    prefs: GruPreferences,
    permissionRefresh: Int,
    focus: MascotFocus = MascotFocus.LIBRARY,
    modifier: Modifier = Modifier,
) {
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
    var draftStep by remember { mutableStateOf(MascotDraftStep.START) }
    var customizationStep by remember { mutableStateOf(MascotCustomizationStep.NAME) }
    var poseChoices by remember { mutableStateOf(MascotPoseChoices()) }
    var preparedAssets by remember { mutableStateOf<PreparedMascotAssets?>(null) }
    var posePreviews by remember { mutableStateOf<Map<String, ImageBitmap>>(emptyMap()) }
    var selectedMasterId by remember { mutableStateOf<String?>(null) }
    var masterPreviews by remember { mutableStateOf<Map<String, ImageBitmap>>(emptyMap()) }
    var creationMascotName by remember { mutableStateOf("") }
    var editTarget by remember { mutableStateOf<CustomMascotEntry?>(null) }
    var editName by remember { mutableStateOf("") }
    val customStore = remember { CustomMascotStore(context) }
    var customMascots by remember { mutableStateOf(customStore.entries()) }
    val scope = rememberCoroutineScope()
    val repository = remember { MascotRepository(MascotApi(FirebaseMascotAuthTokenProvider(), FirebaseMascotAppCheckTokenProvider()), prefs, customStore) }
    val installFailureMessage = stringResource(R.string.gru__mascot_install_failed)
    val picker = rememberLauncherForActivityResult(ActivityResultContracts.PickVisualMedia()) {
        photo = it
        creation = if (it == null) MascotCreationState.Idle else MascotCreationState.PhotoSelected
        draftStep = if (it == null) MascotDraftStep.PHOTO else MascotDraftStep.CONFIRM
    }
    val submitSelected: (Uri) -> Unit = { selected ->
        scope.launch {
            creation = MascotCreationState.Submitting
            submitMascotPhoto(context, repository, selected)
                .onSuccess { creation = it.toCreationState() }
                .onFailure { creation = it.toMascotFailure(prefs.pendingMascotJobId.value) }
        }
    }
    LaunchedEffect(Unit) {
        runCatching { repository.resume() }.onSuccess { job ->
            customMascots = repository.customMascots()
            if (job != null) {
                creation = job.toCreationState()
                if (job.state in setOf("FAILED", "CANCELED")) repository.clearPending()
            }
        }.onFailure { creation = it.toMascotFailure(prefs.pendingMascotJobId.value) }
    }
    val pollingJob = when (val current = creation) {
        is MascotCreationState.Tracking -> current.job
        is MascotCreationState.PosePreparationPending -> current.job
        else -> null
    }
    LaunchedEffect(pollingJob?.jobId) {
        val jobId = pollingJob?.jobId ?: return@LaunchedEffect
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
    val posePending = creation as? MascotCreationState.PosePreparationPending
    val previewJob = awaiting?.job ?: posePending?.job
    LaunchedEffect(previewJob?.jobId, previewJob?.masters) {
        val job = previewJob ?: return@LaunchedEffect
        val masters = job.masters
        selectedMasterId = if (awaiting != null) null else job.masterId
        masterPreviews = emptyMap()
        masterPreviews = masters.mapNotNull { reference ->
            runCatching {
                val bytes = repository.downloadMaster(reference)
                BitmapFactory.decodeByteArray(bytes, 0, bytes.size)?.asImageBitmap()
            }
                .getOrNull()?.let { reference.id to it }
        }.toMap()
    }
    val selectionReady = creation as? MascotCreationState.PoseSelectionReady
    LaunchedEffect(selectionReady?.jobId) {
        val jobId = selectionReady?.jobId ?: return@LaunchedEffect
        runCatching { repository.prepareCompletedMascot(jobId) }
            .onSuccess { prepared ->
                preparedAssets = prepared
                posePreviews = prepared.result.poses.mapNotNull { pose ->
                    val optionId = pose.optionId ?: return@mapNotNull null
                    val bytes = prepared.images[pose.poseId] ?: return@mapNotNull null
                    BitmapFactory.decodeByteArray(bytes, 0, bytes.size)?.asImageBitmap()?.let { optionId to it }
                }.toMap()
                if (posePreviews.size == 12) {
                    customizationStep = MascotCustomizationStep.NAME
                } else {
                    val installed = repository.installPreparedMascot(prepared, MascotPoseChoices(), "Meu mascote")
                    creation = if (installed) MascotCreationState.Completed else MascotCreationState.InstallFailed(
                        jobId, installFailureMessage,
                    )
                }
            }
            .onFailure { creation = it.toMascotFailure(jobId) }
    }
    val selectedCustom = source as? MascotSource.Custom
    Column(
        modifier.clipToBounds().verticalScroll(rememberScrollState()).padding(horizontal = 20.dp, vertical = 8.dp),
        verticalArrangement = Arrangement.spacedBy(20.dp),
    ) {
        if (focus == MascotFocus.LIBRARY) {
            GruBrandBar()
            Text(stringResource(R.string.gru__mascots_title), style = MaterialTheme.typography.headlineMedium)
            MascotPreview(
                source, size, opacity, customStore,
                customMascots.firstOrNull { it.poseSetId == selectedCustom?.poseSetId }?.displayName,
            )
            Text(stringResource(R.string.gru__my_mascots), style = MaterialTheme.typography.titleLarge)
            if (customMascots.isEmpty()) {
                Text(stringResource(R.string.gru__my_mascots_empty), color = MaterialTheme.colorScheme.onSurfaceVariant)
            } else {
                Text(stringResource(R.string.gru__my_mascots_summary), color = MaterialTheme.colorScheme.onSurfaceVariant)
                CustomMascotGallery(
                    selected = source,
                    customMascots = customMascots,
                    selectCustom = { entry -> prefs.selectCustomMascot(entry.poseSetId, entry.masterId) },
                    editCustom = { entry ->
                        editTarget = entry
                        editName = entry.displayName.orEmpty()
                    },
                )
            }
            Text(stringResource(R.string.gru__gru_mascots), style = MaterialTheme.typography.titleLarge)
            BuiltInPicker(source, prefs::setPet)
        } else {
            GruBrandBar()
        }
        if (focus == MascotFocus.CREATE && creation in setOf(MascotCreationState.Idle, MascotCreationState.PhotoSelected)) {
            MascotDraftFlow(
                step = draftStep,
                photo = photo,
                onStart = { draftStep = MascotDraftStep.PHOTO },
                onPickPhoto = { picker.launch(PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly)) },
                onConfirmPhoto = { photo?.let(submitSelected) },
                onBack = { draftStep = draftStep.previous() },
                onCancel = {
                    photo = null
                    creation = MascotCreationState.Idle
                    draftStep = MascotDraftStep.PHOTO
                    repository.clearPending()
                },
            )
        } else if (focus == MascotFocus.CREATE) MascotCreationPanel(
            photo = photo,
            state = creation,
            onPick = { picker.launch(PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly)) },
            onDiscardPhoto = { photo = null; creation = MascotCreationState.Idle; repository.clearPending() },
            onUsePhoto = submitSelected,
            selectedMasterId = selectedMasterId,
            masterPreviews = masterPreviews,
            onSelectMaster = { selectedMasterId = it },
            preparedAssets = preparedAssets,
            posePreviews = posePreviews,
            customizationStep = customizationStep,
            poseChoices = poseChoices,
            mascotName = creationMascotName,
            onMascotNameChange = { creationMascotName = it.take(32) },
            onSelectPose = { role, optionId -> poseChoices = poseChoices.select(role, optionId) },
            onCustomizationNext = { customizationStep = customizationStep.next() },
            onCustomizationBack = { customizationStep = customizationStep.previous() },
            onApprove = { masterId -> scope.launch {
                val awaiting = creation as? MascotCreationState.AwaitingMasterApproval ?: return@launch
                creation = MascotCreationState.Submitting
                runCatching { repository.approve(awaiting.job.jobId, masterId) }
                    .onSuccess {
                        customMascots = repository.customMascots()
                        creation = it.toCreationState()
                    }
                    .onFailure { creation = it.toMascotFailure(awaiting.job.jobId) }
            } },
            onRetryTracking = { scope.launch {
                val jobId = prefs.pendingMascotJobId.value
                runCatching { repository.resume() }
                    .onSuccess { job -> creation = job?.toCreationState() ?: MascotCreationState.Idle }
                    .onFailure { creation = it.toMascotFailure(jobId) }
            } },
            onStartGeneration = { jobId -> scope.launch {
                creation = MascotCreationState.Submitting
                runCatching { repository.startMasterGeneration(jobId) }
                    .onSuccess { creation = it.toCreationState() }
                    .onFailure { creation = it.toMascotFailure(jobId) }
            } },
            onFinishCustomization = { scope.launch {
                val prepared = preparedAssets ?: return@launch
                creation = MascotCreationState.InstallingMascot(prepared.result.poseSetId)
                val installed = runCatching { repository.installPreparedMascot(prepared, poseChoices, creationMascotName) }
                    .getOrDefault(false)
                creation = if (installed) MascotCreationState.Completed else MascotCreationState.InstallFailed(
                    prepared.result.poseSetId, installFailureMessage,
                )
                if (installed) customMascots = repository.customMascots()
            } },
            onCreateAnother = {
                repository.clearPending()
                photo = null
                creation = MascotCreationState.Idle
                poseChoices = MascotPoseChoices()
                preparedAssets = null
                posePreviews = emptyMap()
                creationMascotName = ""
                draftStep = MascotDraftStep.START
            },
            onCancelCreation = { scope.launch {
                val jobId = prefs.pendingMascotJobId.value ?: return@launch
                creation = MascotCreationState.Canceling
                runCatching { repository.cancel(jobId) }
                    .onSuccess { creation = it.toCreationState() }
                    .onFailure { creation = MascotCreationState.CancelPending(jobId) }
            } },
        )
        if (focus == MascotFocus.LIBRARY) {
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
        }
        Spacer(Modifier.height(12.dp))
    }
    editTarget?.let { target ->
        MascotNameEditorDialog(
            initialName = editName,
            onDismiss = { editTarget = null },
            onSave = { name ->
                customStore.rename(target.poseSetId, name).also { saved ->
                    if (saved) {
                        customMascots = customStore.entries()
                        editTarget = null
                    }
                }
            },
        )
    }
}

internal fun MascotDraftStep.next(): MascotDraftStep = when (this) {
    MascotDraftStep.START -> MascotDraftStep.PHOTO
    MascotDraftStep.PHOTO -> MascotDraftStep.CONFIRM
    MascotDraftStep.CONFIRM -> MascotDraftStep.CONFIRM
}

internal fun MascotDraftStep.previous(): MascotDraftStep = when (this) {
    MascotDraftStep.START, MascotDraftStep.PHOTO -> MascotDraftStep.START
    MascotDraftStep.CONFIRM -> MascotDraftStep.PHOTO
}

internal fun MascotCustomizationStep.next(): MascotCustomizationStep = when (this) {
    MascotCustomizationStep.NAME -> MascotCustomizationStep.NORMAL
    MascotCustomizationStep.NORMAL -> MascotCustomizationStep.LISTENING
    MascotCustomizationStep.LISTENING -> MascotCustomizationStep.TRANSCRIBING
    MascotCustomizationStep.TRANSCRIBING -> MascotCustomizationStep.TRANSCRIBING
}

internal fun MascotCustomizationStep.previous(): MascotCustomizationStep = when (this) {
    MascotCustomizationStep.NAME -> MascotCustomizationStep.NAME
    MascotCustomizationStep.NORMAL -> MascotCustomizationStep.NAME
    MascotCustomizationStep.LISTENING -> MascotCustomizationStep.NORMAL
    MascotCustomizationStep.TRANSCRIBING -> MascotCustomizationStep.LISTENING
}

private suspend fun submitMascotPhoto(
    context: Context,
    repository: MascotRepository,
    selected: Uri,
): Result<com.pguillen.gru.mascot.MascotJobResponse> {
    val started = MascotTelemetry.mark()
    return runCatching {
        val originalContentType = context.contentResolver.getType(selected) ?: "unknown"
        val prepared = context.prepareMascotPhoto(selected)
        MascotTelemetry.info(
            "photo_prepare", started,
            mapOf(
                "outcome" to "success",
                "original_content_type" to originalContentType,
                "upload_content_type" to prepared.contentType,
                "image_bytes" to prepared.bytes.size,
                "width" to prepared.width,
                "height" to prepared.height,
            ),
        )
        repository.create(prepared.bytes, prepared.contentType)
    }.onFailure { MascotTelemetry.failure("submit_flow", started, it) }
}

@Composable private fun MascotPreview(source: MascotSource, size: GruPetSize, opacity: Int, store: CustomMascotStore, customName: String?) {
    Column(Modifier.fillMaxWidth(), horizontalAlignment = Alignment.CenterHorizontally) {
        when (source) {
            is MascotSource.BuiltIn -> {
                val option = petOption(source.pet)
                Image(painterResource(option.drawable), stringResource(R.string.gru__preview_description, stringResource(option.name)), contentScale = ContentScale.Fit, modifier = Modifier.size(144.dp * size.scale).alpha(opacity / 100f))
                Text(stringResource(option.name), style = MaterialTheme.typography.titleMedium)
            }
            is MascotSource.Custom -> {
                val preview = rememberFileBitmap(store.previewFile(source.poseSetId)?.absolutePath)
                if (preview != null) Image(preview, stringResource(R.string.gru__custom_mascot), contentScale = ContentScale.Fit, modifier = Modifier.size(144.dp * size.scale).alpha(opacity / 100f))
                Text(customName ?: stringResource(R.string.gru__custom_mascot), style = MaterialTheme.typography.titleMedium)
            }
        }
    }
}

@Composable private fun BuiltInPicker(selected: MascotSource, select: (GruPet) -> Unit) {
    PET_OPTIONS.chunked(3).forEach { row ->
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            row.forEach { option ->
                MascotGalleryCard(
                    selected = selected == MascotSource.BuiltIn(option.pet),
                    onClick = { select(option.pet) },
                    image = { Image(painterResource(option.drawable), null, modifier = Modifier.size(64.dp)) },
                    label = stringResource(option.name),
                    modifier = Modifier.weight(1f),
                )
            }
            repeat(3 - row.size) { Spacer(Modifier.weight(1f)) }
        }
    }
}

@Composable private fun CustomMascotGallery(
    selected: MascotSource,
    customMascots: List<CustomMascotEntry>,
    selectCustom: (CustomMascotEntry) -> Unit,
    editCustom: (CustomMascotEntry) -> Unit,
) {
    val cards = customMascots.mapIndexed { index, entry -> entry to (index + 1) }
    cards.chunked(3).forEach { row ->
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            row.forEach { (entry, number) ->
                Box(Modifier.weight(1f)) {
                        MascotGalleryCard(
                            selected = selected == MascotSource.Custom(entry.poseSetId, entry.masterId),
                            onClick = { selectCustom(entry) },
                            image = {
                                rememberFileBitmap(entry.previewPath)?.let {
                                    Image(
                                        it, null,
                                        modifier = Modifier.size(72.dp).clip(RoundedCornerShape(8.dp)),
                                        contentScale = ContentScale.Crop,
                                        alignment = Alignment.TopCenter,
                                    )
                                }
                            },
                            label = entry.displayName ?: stringResource(R.string.gru__personalized_mascot_number, number),
                            modifier = Modifier.fillMaxWidth(),
                        )
                            IconButton(
                                onClick = { editCustom(entry) },
                                modifier = Modifier.align(Alignment.TopEnd).size(36.dp),
                            ) {
                                Icon(Icons.Default.Edit, stringResource(R.string.gru__edit_mascot_name))
                            }
                }
            }
            repeat(3 - row.size) { Spacer(Modifier.weight(1f)) }
        }
    }
}

@Composable private fun MascotNameEditorDialog(
    initialName: String,
    onDismiss: () -> Unit,
    onSave: (String) -> Boolean,
) {
    var draft by remember(initialName) { mutableStateOf(initialName) }
    var saveFailed by remember { mutableStateOf(false) }
    val normalized = normalizeDisplayName(draft)
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(stringResource(R.string.gru__edit_mascot_name)) },
        text = {
            OutlinedTextField(
                value = draft,
                onValueChange = {
                    draft = it.take(CustomMascotStore.MAX_DISPLAY_NAME_LENGTH)
                    saveFailed = false
                },
                label = { Text(stringResource(R.string.gru__mascot_name)) },
                supportingText = {
                    Text(
                        if (saveFailed) stringResource(R.string.gru__mascot_name_save_failed)
                        else stringResource(R.string.gru__mascot_name_hint),
                        color = if (saveFailed) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                },
                isError = saveFailed,
                singleLine = true,
            )
        },
        confirmButton = {
            TextButton(
                onClick = { saveFailed = !onSave(normalized) },
                enabled = normalized.isNotBlank(),
            ) { Text(stringResource(R.string.gru__save_name)) }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text(stringResource(android.R.string.cancel)) } },
    )
}

@Composable private fun MascotGalleryCard(
    selected: Boolean,
    onClick: () -> Unit,
    image: @Composable () -> Unit,
    label: String,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier.semantics { this.selected = selected; role = Role.RadioButton }
            .border(if (selected) 2.dp else 1.dp, if (selected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.outlineVariant, RoundedCornerShape(10.dp))
            .clickable(onClick = onClick).padding(8.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        image()
        Text(label, maxLines = 2, style = MaterialTheme.typography.bodyMedium)
    }
}

@Composable private fun rememberFileBitmap(path: String?): ImageBitmap? = remember(path) {
    path?.let(BitmapFactory::decodeFile)?.asImageBitmap()
}

@Composable private fun MascotCreationPanel(
    photo: Uri?, state: MascotCreationState, onPick: () -> Unit, onDiscardPhoto: () -> Unit,
    onUsePhoto: (Uri) -> Unit, selectedMasterId: String?, masterPreviews: Map<String, ImageBitmap>,
    onSelectMaster: (String) -> Unit, preparedAssets: PreparedMascotAssets?, posePreviews: Map<String, ImageBitmap>,
    customizationStep: MascotCustomizationStep, poseChoices: MascotPoseChoices,
    mascotName: String, onMascotNameChange: (String) -> Unit,
    onSelectPose: (com.pguillen.gru.mascot.MascotPoseRole, String) -> Unit,
    onCustomizationNext: () -> Unit, onCustomizationBack: () -> Unit,
    onApprove: (String) -> Unit, onRetryTracking: () -> Unit,
    onStartGeneration: (String) -> Unit,
    onFinishCustomization: () -> Unit,
    onCreateAnother: () -> Unit,
    onCancelCreation: () -> Unit,
) {
    val retrySubmissionOrTracking = {
        if (photo != null) onUsePhoto(photo) else onRetryTracking()
    }
    when (state) {
        MascotCreationState.Idle -> Button(onClick = onPick, modifier = Modifier.fillMaxWidth()) { Text(stringResource(R.string.gru__choose_photo)) }
        MascotCreationState.PhotoSelected -> Unit
        MascotCreationState.Submitting -> MascotGenerationProgress("Preparando sua criação", "Estamos enviando a foto com segurança.")
        is MascotCreationState.Tracking -> {
            val generatingPoses = state.job.state == "GENERATING_POSES"
            MascotGenerationProgress(
                if (generatingPoses) "Criando 12 poses" else "Criando três personagens",
                if (generatingPoses) "São quatro poses normais, quatro ouvindo e quatro transcrevendo."
                else "Você poderá escolher seu personagem favorito antes de criarmos as poses.",
            )
            OutlinedButton(onClick = onCancelCreation, modifier = Modifier.fillMaxWidth()) { Text(stringResource(R.string.gru__cancel_creation)) }
        }
        is MascotCreationState.GenerationPaused -> {
            Text(
                stringResource(R.string.gru__mascot_waiting_generation),
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Button(onClick = { onStartGeneration(state.job.jobId) }, modifier = Modifier.fillMaxWidth()) {
                Text(stringResource(R.string.gru__continue_creation))
            }
            OutlinedButton(onClick = onCancelCreation, modifier = Modifier.fillMaxWidth()) { Text(stringResource(R.string.gru__cancel_creation)) }
        }
        is MascotCreationState.AwaitingMasterApproval -> {
            MasterChoices(state.job.masters, masterPreviews, selectedMasterId, onSelectMaster, onApprove)
            OutlinedButton(onClick = onCancelCreation, modifier = Modifier.fillMaxWidth()) { Text(stringResource(R.string.gru__discard_master_options)) }
        }
        is MascotCreationState.PosePreparationPending -> {
            MascotGenerationProgress("Criando 12 poses", "Estamos mantendo a identidade escolhida e preparando quatro opções para cada momento.")
            OutlinedButton(onClick = onCancelCreation, modifier = Modifier.fillMaxWidth()) { Text(stringResource(R.string.gru__cancel_creation)) }
        }
        is MascotCreationState.PoseSelectionReady -> if (preparedAssets == null) {
            MascotGenerationProgress("Preparando as galerias", "As imagens estão prontas. Agora estamos trazendo as prévias para você escolher.")
        } else MascotGeneratedFlow(
            customizationStep, poseChoices, mascotName, posePreviews,
            onSelectPose, onMascotNameChange, onCustomizationNext, onCustomizationBack, onFinishCustomization,
        )
        is MascotCreationState.InstallingMascot -> LoadingMessage(R.string.gru__mascot_installing)
        MascotCreationState.Completed -> {
            Text("Seu mascote está pronto!", style = MaterialTheme.typography.headlineSmall)
            Text(stringResource(R.string.gru__mascot_install_complete), color = MaterialTheme.colorScheme.onSurfaceVariant)
            Button(onClick = onCreateAnother, modifier = Modifier.fillMaxWidth()) {
                Text(stringResource(R.string.gru__create_another_mascot))
            }
        }
        is MascotCreationState.InstallFailed -> {
            Text(state.message, color = MaterialTheme.colorScheme.error)
            Button(onClick = onFinishCustomization, modifier = Modifier.fillMaxWidth()) {
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
            Button(onClick = retrySubmissionOrTracking, modifier = Modifier.fillMaxWidth()) { Text(stringResource(R.string.gru__try_again)) }
        }
        is MascotCreationState.RemoteFailed -> {
            Text(state.message, color = MaterialTheme.colorScheme.error)
            if (state.recovery == MascotFailureRecovery.CHOOSE_PHOTO) {
                Button(onClick = onPick, modifier = Modifier.fillMaxWidth()) {
                    Text(stringResource(R.string.gru__try_another_photo))
                }
            } else if (state.recovery == MascotFailureRecovery.RETRY) {
                Button(onClick = retrySubmissionOrTracking, modifier = Modifier.fillMaxWidth()) {
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

@Composable private fun ApprovedMasterPending(
    job: com.pguillen.gru.mascot.MascotJobResponse,
    previews: Map<String, ImageBitmap>,
) {
    val selectedId = job.masterId
    val preview = selectedId?.let(previews::get)
    Column(verticalArrangement = Arrangement.spacedBy(8.dp), horizontalAlignment = Alignment.CenterHorizontally) {
        Text(stringResource(R.string.gru__approved_master), style = MaterialTheme.typography.titleMedium)
        if (preview != null) {
            Image(
                preview,
                stringResource(R.string.gru__approved_master_preview),
                modifier = Modifier.size(160.dp),
                contentScale = ContentScale.Fit,
            )
        }
        Text(
            stringResource(R.string.gru__pose_package_pending),
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
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
        Button(
            onClick = { selectedId?.let(onApprove) },
            enabled = selectedId != null,
            modifier = Modifier.fillMaxWidth(),
        ) {
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

private data class BuiltInOption(val pet: GruPet, val drawable: Int, val name: Int)
private fun petOption(pet: GruPet) = PET_OPTIONS.first { it.pet == pet }
private fun sizeLabel(size: GruPetSize) = when (size) { GruPetSize.SMALL -> R.string.gru__size_small; GruPetSize.MEDIUM -> R.string.gru__size_medium; GruPetSize.LARGE -> R.string.gru__size_large }
private val PET_OPTIONS = listOf(
    BuiltInOption(GruPet.LUME, R.drawable.gru_pet_lume, R.string.gru__pet_lume), BuiltInOption(GruPet.FAISCA, R.drawable.gru_pet_faisca, R.string.gru__pet_faisca), BuiltInOption(GruPet.BIP, R.drawable.gru_pet_bip, R.string.gru__pet_bip), BuiltInOption(GruPet.PINGO, R.drawable.gru_pet_pingo, R.string.gru__pet_pingo), BuiltInOption(GruPet.PUDIM, R.drawable.gru_pet_pudim, R.string.gru__pet_pudim),
)

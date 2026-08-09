package com.pguillen.gru

import android.graphics.BitmapFactory
import android.content.Context
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
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Slider
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Star
import androidx.compose.material.icons.outlined.StarOutline
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
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
import com.pguillen.gru.mascot.MascotSource
import com.pguillen.gru.mascot.CustomMascotStore
import com.pguillen.gru.mascot.CustomMascotEntry
import com.pguillen.gru.mascot.normalizeDisplayName

@Composable
internal fun GruMascotScreen(
    prefs: GruPreferences,
    modifier: Modifier = Modifier,
) {
    val context = LocalContext.current
    val source by prefs.mascotSource.collectAsState()
    val size by prefs.size.collectAsState()
    val opacity by prefs.opacity.collectAsState()
    var editTarget by remember { mutableStateOf<CustomMascotEntry?>(null) }
    var removeTarget by remember { mutableStateOf<CustomMascotEntry?>(null) }
    var editName by remember { mutableStateOf("") }
    val customStore = remember { CustomMascotStore(context) }
    var customMascots by remember { mutableStateOf(customStore.entries()) }
    val selectedCustom = source as? MascotSource.Custom
    Column(
        modifier.clipToBounds().verticalScroll(rememberScrollState()).padding(horizontal = 20.dp, vertical = 8.dp),
        verticalArrangement = Arrangement.spacedBy(20.dp),
    ) {
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
                editCustom = { entry -> editTarget = entry; editName = entry.displayName.orEmpty() },
                toggleFavorite = { entry ->
                    if (customStore.setFavorite(entry.poseSetId, !entry.favorite)) customMascots = customStore.entries()
                },
                removeCustom = { removeTarget = it },
            )
        }
        Text(stringResource(R.string.gru__gru_mascots), style = MaterialTheme.typography.titleLarge)
        BuiltInPicker(source, prefs::setPet)
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
    removeTarget?.let { target ->
        AlertDialog(
            onDismissRequest = { removeTarget = null },
            title = { Text(stringResource(R.string.gru__remove_mascot_title)) },
            text = { Text(stringResource(R.string.gru__remove_mascot_summary)) },
            confirmButton = { TextButton(onClick = {
                if (removeImportedMascotSafely(
                        source = source,
                        entry = target,
                        selectFallback = { prefs.setPet(GruPet.FAISCA) },
                        remove = customStore::remove,
                    )
                ) customMascots = customStore.entries()
                removeTarget = null
            }) { Text(stringResource(R.string.gru__remove_imported_mascot)) } },
            dismissButton = { TextButton(onClick = { removeTarget = null }) { Text(stringResource(android.R.string.cancel)) } },
        )
    }
}

internal fun isActiveCustomMascot(source: MascotSource, entry: CustomMascotEntry): Boolean =
    source == MascotSource.Custom(entry.poseSetId, entry.masterId)

internal fun removeImportedMascotSafely(
    source: MascotSource,
    entry: CustomMascotEntry,
    selectFallback: () -> Unit,
    remove: (String) -> Boolean,
): Boolean {
    if (isActiveCustomMascot(source, entry)) selectFallback()
    return remove(entry.poseSetId)
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
    toggleFavorite: (CustomMascotEntry) -> Unit,
    removeCustom: (CustomMascotEntry) -> Unit,
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
                    if (entry.source == "code_import") {
                        Row(Modifier.align(Alignment.TopEnd)) {
                            IconButton(onClick = { toggleFavorite(entry) }, modifier = Modifier.size(48.dp)) {
                                Icon(
                                    if (entry.favorite) Icons.Default.Star else Icons.Outlined.StarOutline,
                                    stringResource(if (entry.favorite) R.string.gru__remove_favorite else R.string.gru__add_favorite),
                                )
                            }
                            IconButton(onClick = { removeCustom(entry) }, modifier = Modifier.size(48.dp)) {
                                Icon(Icons.Default.Delete, stringResource(R.string.gru__remove_imported_mascot))
                            }
                        }
                    } else {
                        IconButton(onClick = { editCustom(entry) }, modifier = Modifier.align(Alignment.TopEnd).size(48.dp)) {
                            Icon(Icons.Default.Edit, stringResource(R.string.gru__edit_mascot_name))
                        }
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

private data class BuiltInOption(val pet: GruPet, val drawable: Int, val name: Int)
private fun petOption(pet: GruPet) = PET_OPTIONS.first { it.pet == pet }
private fun sizeLabel(size: GruPetSize) = when (size) { GruPetSize.SMALL -> R.string.gru__size_small; GruPetSize.MEDIUM -> R.string.gru__size_medium; GruPetSize.LARGE -> R.string.gru__size_large }
private val PET_OPTIONS = listOf(
    BuiltInOption(GruPet.LUME, R.drawable.gru_pet_lume, R.string.gru__pet_lume), BuiltInOption(GruPet.FAISCA, R.drawable.gru_pet_faisca, R.string.gru__pet_faisca), BuiltInOption(GruPet.BIP, R.drawable.gru_pet_bip, R.string.gru__pet_bip), BuiltInOption(GruPet.PINGO, R.drawable.gru_pet_pingo, R.string.gru__pet_pingo), BuiltInOption(GruPet.PUDIM, R.drawable.gru_pet_pudim, R.string.gru__pet_pudim),
)

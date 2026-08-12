package com.pguillen.gru

import android.graphics.BitmapFactory
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.filled.Star
import androidx.compose.material.icons.outlined.StarOutline
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Slider
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.clipToBounds
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.pguillen.gru.mascot.CustomMascotEntry
import com.pguillen.gru.mascot.CustomMascotStore
import com.pguillen.gru.mascot.MascotSource
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

@Composable
internal fun GruMascotScreen(
    prefs: GruPreferences,
    modifier: Modifier = Modifier,
) {
    val context = LocalContext.current
    val source by prefs.mascotSource.collectAsState()
    val size by prefs.size.collectAsState()
    val opacity by prefs.opacity.collectAsState()
    val customStore = remember { CustomMascotStore(context) }
    val allEntries by remember(customStore) { customStore.observeEntries() }
        .collectAsState(initial = customStore.entries())
    val imported = importedMascotEntries(allEntries)
    val selectedCustom = source as? MascotSource.Custom
    var removeTarget by remember { mutableStateOf<CustomMascotEntry?>(null) }
    var removeFailed by remember { mutableStateOf(false) }

    BoxWithConstraints(modifier) {
        val columns = if (maxWidth < 360.dp || LocalDensity.current.fontScale >= 1.5f) 2 else 3
        Column(
            Modifier.clipToBounds().verticalScroll(rememberScrollState())
                .padding(horizontal = 16.dp, vertical = 8.dp),
            verticalArrangement = Arrangement.spacedBy(24.dp),
        ) {
            GruBrandBar()
            Text(stringResource(R.string.gru__mascots_title), style = MaterialTheme.typography.headlineMedium)

            MascotSection(title = stringResource(R.string.gru__current_mascot)) {
                CurrentMascotCard(
                    source = source,
                    size = size,
                    opacity = opacity,
                    store = customStore,
                    customName = allEntries.firstOrNull { it.poseSetId == selectedCustom?.poseSetId }?.displayName,
                )
            }

            MascotSection(title = stringResource(R.string.gru__gru_mascots)) {
                BuiltInPicker(source, prefs::setPet, columns)
            }

            MascotSection(
                title = stringResource(R.string.gru__my_mascots),
                summary = if (imported.isEmpty()) stringResource(R.string.gru__my_mascots_empty) else null,
            ) {
                if (imported.isNotEmpty()) {
                    ImportedMascotGallery(
                        selected = source,
                        mascots = imported,
                        columns = columns,
                        select = { prefs.selectCustomMascot(it.poseSetId, it.masterId) },
                        toggleFavorite = { customStore.setFavorite(it.poseSetId, !it.favorite) },
                        move = { entry, offset -> customStore.reorderImported(entry.poseSetId, offset) },
                        remove = { target -> removeFailed = false; removeTarget = target },
                    )
                }
            }

            MascotSection(title = stringResource(R.string.gru__appearance)) {
                AppearanceControls(size, opacity, prefs)
            }
            Spacer(Modifier.height(12.dp))
        }
    }

    removeTarget?.let { target ->
        AlertDialog(
            onDismissRequest = { removeTarget = null; removeFailed = false },
            title = { Text(stringResource(R.string.gru__remove_mascot_title)) },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text(stringResource(R.string.gru__remove_mascot_summary))
                    if (removeFailed) Text(
                        stringResource(R.string.gru__remove_mascot_failed),
                        color = MaterialTheme.colorScheme.error,
                    )
                }
            },
            confirmButton = {
                TextButton(onClick = {
                    val removed = removeImportedMascotSafely(
                        source = source,
                        entry = target,
                        selectFallback = { prefs.setPet(GruPet.FAISCA) },
                        restoreSelection = { prefs.selectCustomMascot(target.poseSetId, target.masterId) },
                        remove = customStore::remove,
                    )
                    removeFailed = !removed
                    if (removed) removeTarget = null
                }) { Text(stringResource(R.string.gru__remove_imported_mascot)) }
            },
            dismissButton = {
                TextButton(onClick = { removeTarget = null; removeFailed = false }) {
                    Text(stringResource(android.R.string.cancel))
                }
            },
        )
    }
}

internal fun isActiveCustomMascot(source: MascotSource, entry: CustomMascotEntry): Boolean =
    source == MascotSource.Custom(entry.poseSetId, entry.masterId)

internal fun importedMascotEntries(entries: List<CustomMascotEntry>): List<CustomMascotEntry> =
    entries.filter { it.source == CustomMascotStore.SOURCE_CODE_IMPORT }

internal fun removeImportedMascotSafely(
    source: MascotSource,
    entry: CustomMascotEntry,
    selectFallback: () -> Unit,
    restoreSelection: () -> Unit = {},
    remove: (String) -> Boolean,
): Boolean {
    val wasActive = isActiveCustomMascot(source, entry)
    if (wasActive) selectFallback()
    val removed = remove(entry.poseSetId)
    if (!removed && wasActive) restoreSelection()
    return removed
}

@Composable
private fun MascotSection(title: String, summary: String? = null, content: @Composable () -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text(title, style = MaterialTheme.typography.titleLarge, color = MaterialTheme.colorScheme.primary)
        summary?.let { Text(it, color = MaterialTheme.colorScheme.onSurfaceVariant) }
        content()
    }
}

@Composable
private fun CurrentMascotCard(
    source: MascotSource,
    size: GruPetSize,
    opacity: Int,
    store: CustomMascotStore,
    customName: String?,
) {
    Surface(
        shape = RoundedCornerShape(16.dp),
        color = MaterialTheme.colorScheme.surfaceContainerLow,
        border = BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Column(
            Modifier.padding(20.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            when (source) {
                is MascotSource.BuiltIn -> {
                    val option = petOption(source.pet)
                    Image(
                        painterResource(option.drawable),
                        stringResource(R.string.gru__preview_description, stringResource(option.name)),
                        contentScale = ContentScale.Fit,
                        modifier = Modifier.size((112.dp * size.scale).coerceAtMost(152.dp)).alpha(opacity / 100f),
                    )
                    Text(stringResource(option.name), style = MaterialTheme.typography.titleMedium)
                    Text(stringResource(R.string.gru__official_mascot), color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                is MascotSource.Custom -> {
                    val preview by rememberFileBitmap(store.previewFile(source.poseSetId)?.absolutePath, 512)
                    preview?.let {
                        Image(
                            it,
                            customName ?: stringResource(R.string.gru__custom_mascot),
                            contentScale = ContentScale.Fit,
                            modifier = Modifier.size((112.dp * size.scale).coerceAtMost(152.dp)).alpha(opacity / 100f),
                        )
                    }
                    Text(customName ?: stringResource(R.string.gru__custom_mascot), style = MaterialTheme.typography.titleMedium)
                    Text(stringResource(R.string.gru__imported_from_perch), color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
    }
}

@Composable
private fun BuiltInPicker(selected: MascotSource, select: (GruPet) -> Unit, columns: Int) {
    PET_OPTIONS.chunked(columns).forEach { row ->
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            row.forEach { option ->
                MascotGalleryCard(
                    selected = selected == MascotSource.BuiltIn(option.pet),
                    onClick = { select(option.pet) },
                    image = {
                        Image(
                            painterResource(option.drawable),
                            null,
                            contentScale = ContentScale.Fit,
                            modifier = Modifier.size(if (columns == 3) 56.dp else 72.dp),
                        )
                    },
                    label = stringResource(option.name),
                    modifier = Modifier.weight(1f),
                )
            }
            repeat(columns - row.size) { Spacer(Modifier.weight(1f)) }
        }
    }
}

@Composable
private fun ImportedMascotGallery(
    selected: MascotSource,
    mascots: List<CustomMascotEntry>,
    columns: Int,
    select: (CustomMascotEntry) -> Unit,
    toggleFavorite: (CustomMascotEntry) -> Unit,
    move: (CustomMascotEntry, Int) -> Unit,
    remove: (CustomMascotEntry) -> Unit,
) {
    mascots.chunked(columns).forEachIndexed { rowIndex, row ->
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            row.forEachIndexed { columnIndex, entry ->
                val index = rowIndex * columns + columnIndex
                ImportedMascotCard(
                    entry = entry,
                    selected = selected == MascotSource.Custom(entry.poseSetId, entry.masterId),
                    canMoveBefore = index > 0,
                    canMoveAfter = index < mascots.lastIndex,
                    select = { select(entry) },
                    toggleFavorite = { toggleFavorite(entry) },
                    moveBefore = { move(entry, -1) },
                    moveAfter = { move(entry, 1) },
                    remove = { remove(entry) },
                    modifier = Modifier.weight(1f),
                )
            }
            repeat(columns - row.size) { Spacer(Modifier.weight(1f)) }
        }
    }
}

@Composable
private fun ImportedMascotCard(
    entry: CustomMascotEntry,
    selected: Boolean,
    canMoveBefore: Boolean,
    canMoveAfter: Boolean,
    select: () -> Unit,
    toggleFavorite: () -> Unit,
    moveBefore: () -> Unit,
    moveAfter: () -> Unit,
    remove: () -> Unit,
    modifier: Modifier = Modifier,
) {
    var menuExpanded by remember { mutableStateOf(false) }
    Column(modifier, horizontalAlignment = Alignment.CenterHorizontally) {
        MascotGalleryCard(
            selected = selected,
            onClick = select,
            image = {
                val preview by rememberFileBitmap(entry.previewPath, 256)
                preview?.let {
                    Image(
                        it,
                        null,
                        modifier = Modifier.size(64.dp).clip(RoundedCornerShape(12.dp)),
                        contentScale = ContentScale.Fit,
                    )
                }
            },
            label = entry.displayName ?: stringResource(R.string.gru__custom_mascot),
            modifier = Modifier.fillMaxWidth(),
        )
        Row(verticalAlignment = Alignment.CenterVertically) {
            IconButton(onClick = toggleFavorite, modifier = Modifier.size(48.dp)) {
                Icon(
                    if (entry.favorite) Icons.Default.Star else Icons.Outlined.StarOutline,
                    stringResource(if (entry.favorite) R.string.gru__remove_favorite else R.string.gru__add_favorite),
                    tint = if (entry.favorite) GruColors.Gold else MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Box {
                IconButton(onClick = { menuExpanded = true }, modifier = Modifier.size(48.dp)) {
                    Icon(Icons.Default.MoreVert, stringResource(R.string.gru__mascot_actions, entry.displayName.orEmpty()))
                }
                DropdownMenu(expanded = menuExpanded, onDismissRequest = { menuExpanded = false }) {
                    DropdownMenuItem(
                        text = { Text(stringResource(R.string.gru__move_mascot_before)) },
                        enabled = canMoveBefore,
                        onClick = { menuExpanded = false; moveBefore() },
                    )
                    DropdownMenuItem(
                        text = { Text(stringResource(R.string.gru__move_mascot_after)) },
                        enabled = canMoveAfter,
                        onClick = { menuExpanded = false; moveAfter() },
                    )
                    DropdownMenuItem(
                        text = { Text(stringResource(R.string.gru__remove_imported_mascot), color = MaterialTheme.colorScheme.error) },
                        leadingIcon = { Icon(Icons.Default.Delete, null, tint = MaterialTheme.colorScheme.error) },
                        onClick = { menuExpanded = false; remove() },
                    )
                }
            }
        }
    }
}

@Composable
private fun AppearanceControls(size: GruPetSize, opacity: Int, prefs: GruPreferences) {
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text(stringResource(R.string.gru__size), style = MaterialTheme.typography.titleMedium)
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            GruPetSize.entries.forEach { option ->
                FilterChip(
                    selected = option == size,
                    onClick = { prefs.setSize(option) },
                    label = { Text(stringResource(sizeLabel(option)), textAlign = TextAlign.Center) },
                    modifier = Modifier.weight(1f).heightIn(min = 48.dp),
                )
            }
        }
        Text(stringResource(R.string.gru__opacity, opacity), style = MaterialTheme.typography.titleMedium)
        Slider(
            value = opacity.toFloat(),
            onValueChange = { prefs.setOpacity(it.toInt()) },
            valueRange = 40f..100f,
            steps = 5,
            modifier = Modifier.semantics { stateDescription = "$opacity%" },
        )
    }
}

@Composable
private fun MascotGalleryCard(
    selected: Boolean,
    onClick: () -> Unit,
    image: @Composable () -> Unit,
    label: String,
    modifier: Modifier = Modifier,
) {
    val selectionText = stringResource(if (selected) R.string.gru__selected else R.string.gru__not_selected)
    Surface(
        onClick = onClick,
        shape = RoundedCornerShape(12.dp),
        color = if (selected) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.surfaceContainerLow,
        border = BorderStroke(
            if (selected) 2.dp else 1.dp,
            if (selected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.outlineVariant,
        ),
        modifier = modifier.heightIn(min = 112.dp).semantics(mergeDescendants = true) {
            this.selected = selected
            role = Role.RadioButton
            stateDescription = selectionText
            contentDescription = label
        },
    ) {
        Box(Modifier.padding(8.dp)) {
            Column(
                Modifier.fillMaxWidth().align(Alignment.Center),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                image()
                Text(label, maxLines = 2, textAlign = TextAlign.Center, style = MaterialTheme.typography.bodyMedium)
            }
            if (selected) Icon(
                Icons.Default.CheckCircle,
                null,
                tint = MaterialTheme.colorScheme.primary,
                modifier = Modifier.align(Alignment.TopEnd).size(20.dp),
            )
        }
    }
}

@Composable
private fun rememberFileBitmap(path: String?, targetPixels: Int): androidx.compose.runtime.State<ImageBitmap?> =
    produceState<ImageBitmap?>(initialValue = null, key1 = path, key2 = targetPixels) {
        value = withContext(Dispatchers.IO) { decodeSampledBitmap(path, targetPixels) }
    }

private fun decodeSampledBitmap(path: String?, targetPixels: Int): ImageBitmap? {
    if (path == null) return null
    val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
    BitmapFactory.decodeFile(path, bounds)
    var sample = 1
    while (bounds.outWidth / sample > targetPixels * 2 || bounds.outHeight / sample > targetPixels * 2) sample *= 2
    return BitmapFactory.decodeFile(path, BitmapFactory.Options().apply { inSampleSize = sample })?.asImageBitmap()
}

private data class BuiltInOption(val pet: GruPet, val drawable: Int, val name: Int)
private fun petOption(pet: GruPet) = PET_OPTIONS.first { it.pet == pet }
private fun sizeLabel(size: GruPetSize) = when (size) {
    GruPetSize.SMALL -> R.string.gru__size_small
    GruPetSize.MEDIUM -> R.string.gru__size_medium
    GruPetSize.LARGE -> R.string.gru__size_large
}

/** Five official assets exist today; the three-column layout intentionally supports a sixth. */
private val PET_OPTIONS = listOf(
    BuiltInOption(GruPet.LUME, R.drawable.gru_pet_lume, R.string.gru__pet_lume),
    BuiltInOption(GruPet.FAISCA, R.drawable.gru_pet_faisca, R.string.gru__pet_faisca),
    BuiltInOption(GruPet.BIP, R.drawable.gru_pet_bip, R.string.gru__pet_bip),
    BuiltInOption(GruPet.PINGO, R.drawable.gru_pet_pingo, R.string.gru__pet_pingo),
    BuiltInOption(GruPet.PUDIM, R.drawable.gru_pet_pudim, R.string.gru__pet_pudim),
)

internal const val PLANNED_BUILT_IN_MASCOT_COUNT = 6
internal val currentBuiltInMascotCount: Int get() = PET_OPTIONS.size

package com.pguillen.gru

import android.graphics.BitmapFactory
import android.net.Uri
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.role
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.pguillen.gru.mascot.MascotPoseChoices
import com.pguillen.gru.mascot.MascotPoseOption
import com.pguillen.gru.mascot.MascotPoseRole
import com.pguillen.gru.mascot.poseOptions

internal enum class MascotDraftStep { START, PHOTO, CONFIRM }
internal enum class MascotCustomizationStep { NAME, NORMAL, LISTENING, TRANSCRIBING }

@Composable
internal fun MascotDraftFlow(
    step: MascotDraftStep,
    photo: Uri?,
    onStart: () -> Unit,
    onPickPhoto: () -> Unit,
    onConfirmPhoto: () -> Unit,
    onBack: () -> Unit,
    onCancel: () -> Unit,
) {
    when (step) {
        MascotDraftStep.START -> MascotStartStep(onStart)
        MascotDraftStep.PHOTO -> MascotPhotoPickerStep(onPickPhoto, onBack)
        MascotDraftStep.CONFIRM -> MascotPhotoConfirmStep(photo, onConfirmPhoto, onPickPhoto, onCancel)
    }
}

@Composable
internal fun MascotGenerationProgress(title: String, detail: String) {
    CreationStepFrame(title = title, summary = detail) {
        Image(
            painter = painterResource(R.drawable.gru_brand_master), contentDescription = null,
            modifier = Modifier.fillMaxWidth().heightIn(min = 150.dp, max = 210.dp), contentScale = ContentScale.Fit,
        )
        LinearProgressIndicator(Modifier.fillMaxWidth())
        Text(
            "Estimativa inicial: cerca de 2 a 4 minutos no total. O tempo varia conforme a fila.",
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            style = MaterialTheme.typography.bodySmall,
            textAlign = TextAlign.Center,
        )
    }
}

@Composable
internal fun MascotGeneratedFlow(
    step: MascotCustomizationStep,
    choices: MascotPoseChoices,
    name: String,
    previews: Map<String, ImageBitmap>,
    onSelectPose: (MascotPoseRole, String) -> Unit,
    onNameChange: (String) -> Unit,
    onNext: () -> Unit,
    onBack: () -> Unit,
    onFinish: () -> Unit,
) {
    when (step) {
        MascotCustomizationStep.NAME -> MascotNameStep(name, previews.values.firstOrNull(), onNameChange, onNext)
        MascotCustomizationStep.NORMAL -> PoseChoiceStep(step, MascotPoseRole.NORMAL, choices.normal, previews, onSelectPose, onNext, onBack)
        MascotCustomizationStep.LISTENING -> PoseChoiceStep(step, MascotPoseRole.LISTENING, choices.listening, previews, onSelectPose, onNext, onBack)
        MascotCustomizationStep.TRANSCRIBING -> PoseChoiceStep(step, MascotPoseRole.TRANSCRIBING, choices.transcribing, previews, onSelectPose, onFinish, onBack)
    }
}

@Composable
private fun MascotStartStep(onStart: () -> Unit) {
    CreationStepFrame(title = "Crie um companheiro só seu", summary = "Envie uma foto, escolha seu personagem e veja as 12 poses antes de decidir.") {
        Image(painter = painterResource(R.drawable.gru_brand_master), contentDescription = null, modifier = Modifier.fillMaxWidth().heightIn(min = 190.dp, max = 260.dp), contentScale = ContentScale.Fit)
        GoldPrimaryButton("Começar", onStart)
        Text("Você revisa cada imagem antes de usar o mascote.", color = MaterialTheme.colorScheme.onSurfaceVariant, textAlign = TextAlign.Center)
    }
}

@Composable
private fun MascotPhotoPickerStep(onPick: () -> Unit, onBack: () -> Unit) {
    CreationStepFrame(1, 2, "Envie uma foto", "Ela será referência para identidade, cores e detalhes — não para copiar a pose.") {
        GruPanel(accent = GruColors.Cyan) {
            Column(Modifier.fillMaxWidth().padding(vertical = 20.dp), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("FOTO", color = GruColors.Cyan, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                Text("Pessoa ou animal bem visível", color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
        GoldPrimaryButton("Escolher foto", onPick)
        StepBackButton(onBack)
    }
}

@Composable
private fun MascotPhotoConfirmStep(photo: Uri?, onConfirm: () -> Unit, onChange: () -> Unit, onCancel: () -> Unit) {
    CreationStepFrame(2, 2, "Confira sua foto", "Primeiro criaremos três personagens para você escolher.") {
        PhotoPreview(photo, "Foto escolhida para servir de referência")
        GoldPrimaryButton("Criar opções", onConfirm, photo != null)
        OutlinedButton(onClick = onChange, modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) { Text("Trocar foto") }
        StepBackButton(onCancel)
    }
}

@Composable
private fun MascotNameStep(name: String, preview: ImageBitmap?, onNameChange: (String) -> Unit, onNext: () -> Unit) {
    CreationStepFrame(1, 4, "Como ele vai se chamar?", "Dê um nome ao personagem que você escolheu.") {
        preview?.let { Image(bitmap = it, contentDescription = "Prévia do mascote escolhido", modifier = Modifier.fillMaxWidth().heightIn(min = 170.dp, max = 230.dp), contentScale = ContentScale.Fit) }
        OutlinedTextField(
            value = name, onValueChange = { onNameChange(it.take(32)) },
            label = { Text("Nome do mascote") }, supportingText = { Text("Até 32 caracteres") },
            singleLine = true, modifier = Modifier.fillMaxWidth(),
        )
        GoldPrimaryButton("Continuar", onNext, name.trim().isNotEmpty())
    }
}

@Composable
private fun PoseChoiceStep(
    step: MascotCustomizationStep,
    role: MascotPoseRole,
    selectedId: String,
    previews: Map<String, ImageBitmap>,
    onSelect: (MascotPoseRole, String) -> Unit,
    onNext: () -> Unit,
    onBack: () -> Unit,
) {
    val (title, summary) = when (role) {
        MascotPoseRole.NORMAL -> "Pose normal" to "Escolha como ele fica quando está pronto para ajudar."
        MascotPoseRole.LISTENING -> "Pose ouvindo" to "Escolha como ele demonstra que está escutando você."
        MascotPoseRole.TRANSCRIBING -> "Pose transcrevendo" to "Escolha como ele aparece enquanto transforma voz em texto."
    }
    CreationStepFrame(step.ordinal + 1, 4, title, summary) {
        poseOptions(role).chunked(2).forEach { row ->
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                row.forEach { option -> PoseOptionCard(option, previews[option.id], option.id == selectedId, { onSelect(role, option.id) }, Modifier.weight(1f)) }
            }
        }
        GoldPrimaryButton(if (step == MascotCustomizationStep.TRANSCRIBING) "Concluir" else "Continuar", onNext)
        StepBackButton(onBack)
    }
}

@Composable
private fun PoseOptionCard(option: MascotPoseOption, preview: ImageBitmap?, selected: Boolean, onClick: () -> Unit, modifier: Modifier) {
    val border = if (selected) GruColors.Cyan else MaterialTheme.colorScheme.outlineVariant
    Card(
        modifier = modifier.heightIn(min = 205.dp).semantics {
            this.selected = selected; role = Role.RadioButton
            contentDescription = "${option.label}. ${option.description}${if (selected) ", selecionada" else ""}"
        }.clickable(enabled = preview != null, onClick = onClick),
        shape = RoundedCornerShape(18.dp), border = BorderStroke(if (selected) 2.dp else 1.dp, border),
        colors = CardDefaults.cardColors(containerColor = if (selected) MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.35f) else MaterialTheme.colorScheme.surface),
    ) {
        Column(Modifier.padding(10.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Box(Modifier.fillMaxWidth().aspectRatio(1f).clip(RoundedCornerShape(14.dp)).background(MaterialTheme.colorScheme.surfaceVariant), contentAlignment = Alignment.Center) {
                if (preview != null) Image(bitmap = preview, contentDescription = null, modifier = Modifier.fillMaxWidth(), contentScale = ContentScale.Fit)
                else Text("Preparando prévia", style = MaterialTheme.typography.bodySmall, textAlign = TextAlign.Center)
            }
            Text(option.label, style = MaterialTheme.typography.titleSmall)
            if (selected) Text("✓ Selecionada", color = GruColors.Cyan, style = MaterialTheme.typography.labelLarge)
        }
    }
}

@Composable
private fun CreationStepFrame(step: Int? = null, total: Int = 0, title: String, summary: String, content: @Composable ColumnScope.() -> Unit) {
    Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(16.dp), horizontalAlignment = Alignment.CenterHorizontally) {
        if (step != null) {
            Text("PASSO $step DE $total", color = GruColors.Gold, style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.Bold)
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(5.dp)) {
                repeat(total) { index -> Box(Modifier.weight(1f).heightIn(min = 4.dp).background(if (index < step) GruColors.Cyan else MaterialTheme.colorScheme.outlineVariant, RoundedCornerShape(50))) }
            }
        }
        Text(title, style = MaterialTheme.typography.headlineMedium, textAlign = TextAlign.Center)
        Text(summary, color = MaterialTheme.colorScheme.onSurfaceVariant, textAlign = TextAlign.Center)
        content()
    }
}

@Composable private fun GoldPrimaryButton(label: String, onClick: () -> Unit, enabled: Boolean = true) {
    Button(onClick, Modifier.fillMaxWidth().heightIn(min = 52.dp), enabled, colors = ButtonDefaults.buttonColors(containerColor = GruColors.Gold, contentColor = GruColors.Night)) { Text(label, fontWeight = FontWeight.Bold) }
}

@Composable private fun StepBackButton(onBack: () -> Unit) {
    OutlinedButton(onClick = onBack, modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) { Text("Voltar") }
}

@Composable private fun PhotoPreview(uri: Uri?, description: String) {
    val context = LocalContext.current
    val preview = remember(uri) { uri?.let { context.contentResolver.openInputStream(it)?.use(BitmapFactory::decodeStream)?.asImageBitmap() } }
    Box(Modifier.fillMaxWidth().aspectRatio(1.25f).clip(RoundedCornerShape(20.dp)).background(MaterialTheme.colorScheme.surfaceVariant), contentAlignment = Alignment.Center) {
        if (preview != null) Image(bitmap = preview, contentDescription = description, modifier = Modifier.fillMaxWidth(), contentScale = ContentScale.Fit)
        else Text("Nenhuma foto selecionada", color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

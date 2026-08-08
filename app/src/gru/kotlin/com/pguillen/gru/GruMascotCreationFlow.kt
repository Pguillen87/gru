package com.pguillen.gru

import android.graphics.BitmapFactory
import android.net.Uri
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
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

internal enum class MascotDraftStep {
    START, PHOTO, CONFIRM, NORMAL, LISTENING, TRANSCRIBING, NAME, REVIEW,
}

@Composable
internal fun MascotDraftFlow(
    step: MascotDraftStep,
    photo: Uri?,
    choices: MascotPoseChoices,
    name: String,
    onStart: () -> Unit,
    onPickPhoto: () -> Unit,
    onConfirmPhoto: () -> Unit,
    onSelectPose: (MascotPoseRole, String) -> Unit,
    onNameChange: (String) -> Unit,
    onNext: () -> Unit,
    onBack: () -> Unit,
    onSubmit: () -> Unit,
    onCancel: () -> Unit,
) {
    when (step) {
        MascotDraftStep.START -> MascotStartStep(onStart)
        MascotDraftStep.PHOTO -> MascotPhotoPickerStep(onPickPhoto, onBack)
        MascotDraftStep.CONFIRM -> MascotPhotoConfirmStep(photo, onConfirmPhoto, onPickPhoto, onCancel)
        MascotDraftStep.NORMAL -> PoseChoiceStep(step, MascotPoseRole.NORMAL, choices.normal, onSelectPose, onNext, onBack)
        MascotDraftStep.LISTENING -> PoseChoiceStep(step, MascotPoseRole.LISTENING, choices.listening, onSelectPose, onNext, onBack)
        MascotDraftStep.TRANSCRIBING -> PoseChoiceStep(step, MascotPoseRole.TRANSCRIBING, choices.transcribing, onSelectPose, onNext, onBack)
        MascotDraftStep.NAME -> MascotNameStep(name, onNameChange, onNext, onBack)
        MascotDraftStep.REVIEW -> MascotReviewStep(photo, choices, name, onSubmit, onBack)
    }
}

@Composable
private fun MascotStartStep(onStart: () -> Unit) {
    CreationStepFrame(title = "Crie um companheiro só seu", summary = "Uma foto ajuda o Gru a entender a identidade do personagem. Depois, você escolhe como ele aparece em cada momento.") {
        Image(
            painter = painterResource(R.drawable.gru_brand_master),
            contentDescription = null,
            contentScale = ContentScale.Fit,
            modifier = Modifier.fillMaxWidth().heightIn(min = 190.dp, max = 260.dp),
        )
        GoldPrimaryButton("Começar", onStart)
        Text("Você revisa tudo antes de enviar.", color = MaterialTheme.colorScheme.onSurfaceVariant, textAlign = TextAlign.Center, modifier = Modifier.fillMaxWidth())
    }
}

@Composable
private fun MascotPhotoPickerStep(onPick: () -> Unit, onBack: () -> Unit) {
    CreationStepFrame(1, "Envie uma foto", "Use uma imagem nítida. Ela será referência para identidade, cores e detalhes — não para copiar a pose.") {
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
    CreationStepFrame(2, "Confira sua foto", "Vamos usar os traços, cores e detalhes para criar um personagem novo em poses próprias.") {
        PhotoPreview(photo, "Foto escolhida para servir de referência")
        GoldPrimaryButton("Continuar", onConfirm, enabled = photo != null)
        OutlinedButton(onClick = onChange, modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) { Text("Trocar foto") }
        StepBackButton(onCancel)
    }
}

@Composable
private fun PoseChoiceStep(
    step: MascotDraftStep,
    role: MascotPoseRole,
    selectedId: String,
    onSelect: (MascotPoseRole, String) -> Unit,
    onNext: () -> Unit,
    onBack: () -> Unit,
) {
    val (title, summary) = when (role) {
        MascotPoseRole.NORMAL -> "Pose normal" to "Como seu mascote fica quando está pronto para ajudar?"
        MascotPoseRole.LISTENING -> "Pose ouvindo" to "Escolha como ele demonstra que está escutando você."
        MascotPoseRole.TRANSCRIBING -> "Pose transcrevendo" to "Escolha como ele aparece enquanto transforma voz em texto."
    }
    CreationStepFrame(step.progressNumber(), title, summary) {
        poseOptions(role).chunked(2).forEach { options ->
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                options.forEach { option -> PoseOptionCard(option, option.id == selectedId, { onSelect(role, option.id) }, Modifier.weight(1f)) }
                if (options.size == 1) Box(Modifier.weight(1f))
            }
        }
        GoldPrimaryButton("Continuar", onNext)
        StepBackButton(onBack)
    }
}

@Composable
private fun PoseOptionCard(option: MascotPoseOption, selected: Boolean, onClick: () -> Unit, modifier: Modifier = Modifier) {
    val border = if (selected) GruColors.Cyan else MaterialTheme.colorScheme.outlineVariant
    Card(
        modifier = modifier.heightIn(min = 150.dp).semantics {
            this.selected = selected
            role = Role.RadioButton
            contentDescription = "${option.label}. ${option.description}${if (selected) ", selecionada" else ""}"
        }.clickable(onClick = onClick),
        shape = RoundedCornerShape(18.dp),
        border = BorderStroke(if (selected) 2.dp else 1.dp, border),
        colors = CardDefaults.cardColors(containerColor = if (selected) MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.35f) else MaterialTheme.colorScheme.surface),
    ) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(9.dp)) {
            Box(Modifier.size(38.dp).clip(RoundedCornerShape(12.dp)).background(border.copy(alpha = 0.18f)), contentAlignment = Alignment.Center) {
                Text(option.label.take(1), color = if (selected) GruColors.Cyan else MaterialTheme.colorScheme.onSurfaceVariant, fontWeight = FontWeight.Bold)
            }
            Text(option.label, style = MaterialTheme.typography.titleMedium)
            Text(option.description, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            if (selected) Text("✓ Selecionada", color = GruColors.Cyan, style = MaterialTheme.typography.labelLarge)
        }
    }
}

@Composable
private fun MascotNameStep(name: String, onNameChange: (String) -> Unit, onNext: () -> Unit, onBack: () -> Unit) {
    CreationStepFrame(6, "Como ele vai se chamar?", "Dê um nome para o novo companheiro do Gru.") {
        Image(painterResource(R.drawable.gru_brand_master), null, Modifier.fillMaxWidth().heightIn(min = 140.dp, max = 200.dp), contentScale = ContentScale.Fit)
        OutlinedTextField(
            value = name,
            onValueChange = { onNameChange(it.take(32)) },
            label = { Text("Nome do mascote") },
            supportingText = { Text("Até 32 caracteres") },
            singleLine = true,
            modifier = Modifier.fillMaxWidth(),
        )
        GoldPrimaryButton("Continuar", onNext, name.trim().isNotEmpty())
        StepBackButton(onBack)
    }
}

@Composable
private fun MascotReviewStep(photo: Uri?, choices: MascotPoseChoices, name: String, onSubmit: () -> Unit, onBack: () -> Unit) {
    CreationStepFrame(7, "Tudo pronto para criar", "Confira suas escolhas. A foto define a identidade; cada seleção abaixo define uma pose diferente.") {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(14.dp), verticalAlignment = Alignment.CenterVertically) {
            PhotoPreview(photo, "Foto de referência", Modifier.size(92.dp))
            Column(Modifier.weight(1f)) {
                Text(name.trim(), style = MaterialTheme.typography.titleLarge)
                Text("3 momentos definidos", color = GruColors.Success)
            }
        }
        ReviewChoice("Pronto", choices.normal)
        ReviewChoice("Ouvindo", choices.listening)
        ReviewChoice("Transcrevendo", choices.transcribing)
        GoldPrimaryButton("Criar meu mascote", onSubmit)
        Text("A geração usa processamento em nuvem e pode levar alguns minutos.", color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodySmall)
        StepBackButton(onBack)
    }
}

@Composable
private fun ReviewChoice(role: String, optionId: String) {
    val option = com.pguillen.gru.mascot.MASCOT_POSE_OPTIONS.first { it.id == optionId }
    Row(Modifier.fillMaxWidth().border(1.dp, MaterialTheme.colorScheme.outlineVariant, RoundedCornerShape(14.dp)).padding(14.dp), horizontalArrangement = Arrangement.SpaceBetween) {
        Text(role, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(option.label, fontWeight = FontWeight.SemiBold)
    }
}

@Composable
private fun CreationStepFrame(step: Int? = null, title: String, summary: String, content: @Composable ColumnScope.() -> Unit) {
    Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(16.dp), horizontalAlignment = Alignment.CenterHorizontally) {
        if (step != null) {
            Text("PASSO $step DE 7", color = GruColors.Gold, style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.Bold)
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(5.dp)) {
                repeat(7) { index -> Box(Modifier.weight(1f).heightIn(min = 4.dp).background(if (index < step) GruColors.Cyan else MaterialTheme.colorScheme.outlineVariant, RoundedCornerShape(50))) }
            }
        }
        Text(title, style = MaterialTheme.typography.headlineMedium, textAlign = TextAlign.Center)
        Text(summary, color = MaterialTheme.colorScheme.onSurfaceVariant, textAlign = TextAlign.Center)
        content()
    }
}

@Composable
private fun GoldPrimaryButton(label: String, onClick: () -> Unit, enabled: Boolean = true) {
    Button(
        onClick = onClick,
        enabled = enabled,
        colors = ButtonDefaults.buttonColors(containerColor = GruColors.Gold, contentColor = GruColors.Night),
        modifier = Modifier.fillMaxWidth().heightIn(min = 52.dp),
    ) { Text(label, fontWeight = FontWeight.Bold) }
}

@Composable
private fun StepBackButton(onBack: () -> Unit) {
    OutlinedButton(onClick = onBack, modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)) { Text("Voltar") }
}

@Composable
private fun PhotoPreview(uri: Uri?, description: String, modifier: Modifier = Modifier.fillMaxWidth().aspectRatio(1.25f)) {
    val context = LocalContext.current
    val preview: ImageBitmap? = remember(uri) { uri?.let { context.contentResolver.openInputStream(it)?.use(BitmapFactory::decodeStream)?.asImageBitmap() } }
    Box(modifier.clip(RoundedCornerShape(20.dp)).background(MaterialTheme.colorScheme.surfaceVariant), contentAlignment = Alignment.Center) {
        if (preview != null) Image(preview, description, Modifier.fillMaxWidth(), contentScale = ContentScale.Fit)
        else Text("Nenhuma foto selecionada", color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

internal fun MascotDraftStep.progressNumber(): Int = when (this) {
    MascotDraftStep.START -> 0
    MascotDraftStep.PHOTO -> 1
    MascotDraftStep.CONFIRM -> 2
    MascotDraftStep.NORMAL -> 3
    MascotDraftStep.LISTENING -> 4
    MascotDraftStep.TRANSCRIBING -> 5
    MascotDraftStep.NAME -> 6
    MascotDraftStep.REVIEW -> 7
}

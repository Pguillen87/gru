package com.pguillen.gru.mascot

enum class MascotPoseRole { NORMAL, LISTENING, TRANSCRIBING }

data class MascotPoseOption(
    val id: String,
    val role: MascotPoseRole,
    val label: String,
    val description: String,
)

data class MascotPoseChoices(
    val normal: String = "normal_attentive",
    val listening: String = "listening_focus",
    val transcribing: String = "transcribing_fast",
) {
    fun asMap(): Map<String, String> = mapOf(
        "normal" to normal,
        "listening" to listening,
        "transcribing" to transcribing,
    )

    fun select(role: MascotPoseRole, optionId: String): MascotPoseChoices = when (role) {
        MascotPoseRole.NORMAL -> copy(normal = optionId)
        MascotPoseRole.LISTENING -> copy(listening = optionId)
        MascotPoseRole.TRANSCRIBING -> copy(transcribing = optionId)
    }
}

val MASCOT_POSE_OPTIONS = listOf(
    MascotPoseOption("normal_attentive", MascotPoseRole.NORMAL, "Atenta", "Pronta e olhando para você."),
    MascotPoseOption("normal_relaxed", MascotPoseRole.NORMAL, "Relaxada", "Calma enquanto espera."),
    MascotPoseOption("normal_curious", MascotPoseRole.NORMAL, "Curiosa", "Leve inclinação e expressão aberta."),
    MascotPoseOption("normal_firm", MascotPoseRole.NORMAL, "Firme", "Postura confiante e estável."),
    MascotPoseOption("listening_focus", MascotPoseRole.LISTENING, "Foco atento", "Inclina-se suavemente para escutar."),
    MascotPoseOption("listening_process", MascotPoseRole.LISTENING, "Processando", "Escuta com concentração tranquila."),
    MascotPoseOption("listening_natural", MascotPoseRole.LISTENING, "Gesto natural", "Um gesto de escuta adequado ao personagem."),
    MascotPoseOption("listening_ready", MascotPoseRole.LISTENING, "Pronta", "Alerta e preparada para responder."),
    MascotPoseOption("transcribing_notes", MascotPoseRole.TRANSCRIBING, "Anotação", "Registra a fala com atenção."),
    MascotPoseOption("transcribing_thought", MascotPoseRole.TRANSCRIBING, "Pensamento profundo", "Organiza as informações com calma."),
    MascotPoseOption("transcribing_fast", MascotPoseRole.TRANSCRIBING, "Digitação ágil", "Transcreve com energia e precisão."),
    MascotPoseOption("transcribing_active", MascotPoseRole.TRANSCRIBING, "Escuta ativa", "Escuta e registra ao mesmo tempo."),
)

fun poseOptions(role: MascotPoseRole): List<MascotPoseOption> =
    MASCOT_POSE_OPTIONS.filter { it.role == role }

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
    MascotPoseOption("normal_attentive", MascotPoseRole.NORMAL, "Pronto e atento", "Preparado para ajudar."),
    MascotPoseOption("normal_relaxed", MascotPoseRole.NORMAL, "Relaxado", "Calmo enquanto espera."),
    MascotPoseOption("normal_curious", MascotPoseRole.NORMAL, "Observador", "Atento ao que acontece."),
    MascotPoseOption("normal_firm", MascotPoseRole.NORMAL, "Espera paciente", "Aguarda com tranquilidade."),
    MascotPoseOption("listening_focus", MascotPoseRole.LISTENING, "Mão na orelha", "Mostra claramente que está ouvindo."),
    MascotPoseOption("listening_process", MascotPoseRole.LISTENING, "Inclinado para ouvir", "Aproxima-se para escutar melhor."),
    MascotPoseOption("listening_natural", MascotPoseRole.LISTENING, "Hang loose ouvindo", "Um gesto descontraído de escuta."),
    MascotPoseOption("listening_ready", MascotPoseRole.LISTENING, "Cabeça inclinada", "Inclina a cabeça com atenção."),
    MascotPoseOption("transcribing_notes", MascotPoseRole.TRANSCRIBING, "Escrevendo", "Registra a fala por escrito."),
    MascotPoseOption("transcribing_fast", MascotPoseRole.TRANSCRIBING, "Digitando", "Transforma a fala em texto."),
    MascotPoseOption("transcribing_thought", MascotPoseRole.TRANSCRIBING, "Organizando ideias", "Organiza as informações com calma."),
    MascotPoseOption("transcribing_active", MascotPoseRole.TRANSCRIBING, "Anotando", "Faz anotações enquanto trabalha."),
)

fun poseOptions(role: MascotPoseRole): List<MascotPoseOption> =
    MASCOT_POSE_OPTIONS.filter { it.role == role }

"""Versioned pose and prompt catalog. Image assets are intentionally external."""

from __future__ import annotations

from dataclasses import dataclass


MASTER_PROMPT_VERSION = "master-v3-identity"
POSE_PROMPT_VERSION = "pose-v4-visual-catalog"
POSE_TEMPLATE_VERSION = "poses-v3-visual-catalog"

MASTER_PROMPT = (
    "Create a clean, friendly, full-body 2D cartoon mascot. Use the supplied photo only as identity evidence, "
    "not as a composition or pose reference. First identify the primary subject and preserve its category exactly: "
    "a human remains a human; an animal remains its exact species. Extract and preserve the subject's distinctive "
    "identity, natural anatomy, colors, markings, facial proportions, coat or feather pattern, and visible clothing "
    "when present. Ignore and do not copy the source pose, gesture, camera angle, crop, framing, lighting, background, "
    "or placement. Repose the subject independently in a balanced neutral standing mascot pose, facing mostly forward, "
    "with the complete body visible and a clear silhouette. "
    "For a human, use normal human ears and anatomy only: never add animal ears, tail, muzzle, paws, fur, "
    "horns, or hybrid features. For an animal, preserve its real species, body plan, coat or feather colors, "
    "markings, ears where naturally applicable, and face. Never turn one species into another. "
    "Single centered character, clear silhouette for small Android sizes, transparent background when supported, "
    "otherwise a plain neutral background; no text, watermark, accessories not present in the reference, or extra subjects."
)

POSE_PROMPT = (
    "Preserve exactly the same GRU mascot identity and subject category from the master reference: "
    "same human or animal species, natural anatomy, colors, markings, face, proportions, and graphic style. "
    "A human must remain fully human with no animal ears, tail, muzzle, paws, fur, horns, or hybrid features. "
    "Treat the master as identity and style evidence only. Do not copy its posture. Apply the requested posture, "
    "gesture, gaze, and expression while keeping every identity detail stable. Single character, clean anatomy, "
    "transparent background when supported, no text, watermark, or extra objects."
)


@dataclass(frozen=True)
class PoseOption:
    option_id: str
    role: str
    label: str
    instruction: str


POSE_OPTIONS = (
    PoseOption("normal_attentive", "normal", "Pronto e atento", "upright ready stance, attentive forward gaze, calm confidence"),
    PoseOption("normal_relaxed", "normal", "Relaxado", "relaxed balanced stance, soft friendly expression, resting naturally"),
    PoseOption("normal_curious", "normal", "Observador", "observing the surroundings with an attentive gaze and composed posture"),
    PoseOption("normal_firm", "normal", "Espera paciente", "patient waiting pose, calm body, gentle expectant expression"),
    PoseOption("listening_focus", "listening", "Mão na orelha", "clear listening gesture with hand, paw, wing, or natural ear oriented toward sound, anatomically appropriate"),
    PoseOption("listening_process", "listening", "Inclinado para ouvir", "leaning the upper body slightly toward the sound with attentive eyes"),
    PoseOption("listening_natural", "listening", "Hang loose ouvindo", "friendly hang-loose listening gesture adapted naturally to the character anatomy"),
    PoseOption("listening_ready", "listening", "Cabeça inclinada", "head tilted toward the sound, alert and clearly listening"),
    PoseOption("transcribing_notes", "transcribing", "Escrevendo", "writing clearly with a simple pencil and note surface, focused expression"),
    PoseOption("transcribing_fast", "transcribing", "Digitando", "typing with focused energy on a simple compact keyboard, clean silhouette"),
    PoseOption("transcribing_thought", "transcribing", "Organizando ideias", "organizing ideas thoughtfully with a composed pose and subtle visual planning gesture"),
    PoseOption("transcribing_active", "transcribing", "Anotando", "taking concise notes with an attentive expression and purposeful writing gesture"),
)


DEFAULT_POSE_CHOICES = {
    "normal": "normal_attentive",
    "listening": "listening_focus",
    "transcribing": "transcribing_fast",
}


def validate_pose_choices(choices: dict[str, str]) -> dict[str, str]:
    if set(choices) != set(DEFAULT_POSE_CHOICES):
        raise ValueError("Exactly one normal, listening, and transcribing pose is required.")
    by_id = {option.option_id: option for option in POSE_OPTIONS}
    normalized: dict[str, str] = {}
    for role, option_id in choices.items():
        option = by_id.get(option_id)
        if option is None or option.role != role:
            raise ValueError(f"Invalid pose option for {role}.")
        normalized[role] = option_id
    return normalized


def pose_option(option_id: str) -> PoseOption:
    return next(option for option in POSE_OPTIONS if option.option_id == option_id)


@dataclass(frozen=True)
class PoseTemplate:
    pose_id: str
    name: str
    difficulty: str
    asset_key: str


POSES = (
    PoseTemplate("pose_01", "idle_standing", "simple", "poses/v1/pose_01.png"),
    PoseTemplate("pose_02", "sitting", "simple", "poses/v1/pose_02.png"),
    PoseTemplate("pose_03", "listening_forward", "intermediate", "poses/v1/pose_03.png"),
    PoseTemplate("pose_04", "thinking", "intermediate", "poses/v1/pose_04.png"),
    PoseTemplate("pose_05", "looking_up", "hard", "poses/v1/pose_05.png"),
    PoseTemplate("pose_06", "celebrating", "hard", "poses/v1/pose_06.png"),
    PoseTemplate("pose_07", "curious", "intermediate", "poses/v1/pose_07.png"),
    PoseTemplate("pose_08", "alert", "simple", "poses/v1/pose_08.png"),
    PoseTemplate("pose_09", "sleeping", "intermediate", "poses/v1/pose_09.png"),
    PoseTemplate("pose_10", "wave", "hard", "poses/v1/pose_10.png"),
)


def consistency_templates() -> tuple[PoseTemplate, PoseTemplate, PoseTemplate]:
    return POSES[0], POSES[2], POSES[4]


def mvp_templates() -> tuple[PoseTemplate, ...]:
    return POSES[:6]

"""Versioned pose and prompt catalog. Image assets are intentionally external."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


MASTER_PROMPT_VERSION = "master-v4-confirmed-category"
POSE_PROMPT_VERSION = "pose-v5-confirmed-identity"
POSE_TEMPLATE_VERSION = "poses-v4-three-selected"

MASTER_PROMPT = (
    "Create one full-body 2D editorial cartoon mascot from the confirmed primary subject. "
    "Use the supplied photo only as identity evidence, never as permission to invent or hybridize anatomy. "
    "Preserve only visual evidence that belongs to the confirmed subject. Do not transfer clothing prints, "
    "background colors, shadows, scenery, or nearby textures onto unrelated body regions. "
    "Recompose one centered character in a balanced neutral pose, facing mostly forward, with a complete body "
    "and a clear silhouette for small Android sizes. Use the approved GRU matte editorial-cartoon finish, "
    "controlled outlines, and transparent background when supported. No text, watermark, additional subject, "
    "invented accessory, duplicated limb, or background scenery."
)

CATEGORY_PROMPTS = {
    "human": (
        "The confirmed subject is a human and must remain anatomically human. Preserve the person's face, skin tone, "
        "body proportions, hair, facial hair, confirmed tattoos, and visible clothing. Clothing colors and prints must "
        "remain on clothing only. Use normal human ears, hands, feet, skin, and facial anatomy."
    ),
    "animal": (
        "The confirmed subject is an animal. Preserve its exact confirmed species, natural body plan, face, colors, "
        "coat, scales, or feather pattern only where naturally applicable. Do not turn it into another species."
    ),
    "object": (
        "The confirmed subject is an object. Preserve its recognizable construction, materials, colors, proportions, "
        "and defining parts. Personify it only through restrained editorial expression without adding animal anatomy."
    ),
    "other": (
        "The confirmed subject belongs to the explicitly described category. Preserve that category, construction, "
        "materials, colors, proportions, and defining features without borrowing anatomy from humans or animals."
    ),
}

CATEGORY_NEGATIVE_PROMPTS = {
    "human": "animal ears, fur, muzzle, paws, tail, horns, feathers, animal markings, hybrid anatomy, clothing pattern on skin",
    "animal": "wrong species, human ears, human skin, species hybrid, invented markings, clothing pattern on fur",
    "object": "animal ears, fur, paws, tail, human skin, species hybrid, organic anatomy",
    "other": "category change, species hybrid, invented anatomy, unrelated materials",
}


def build_master_prompt(identity: Mapping[str, object]) -> str:
    category = str(identity.get("category", "other"))
    label = str(identity.get("label", "confirmed subject"))
    species = str(identity.get("species") or "").strip()
    category_prompt = CATEGORY_PROMPTS.get(category, CATEGORY_PROMPTS["other"])
    identity_line = f"Confirmed subject label: {label}."
    if category == "animal" and species:
        identity_line += f" Confirmed species: {species}."
    return " ".join((MASTER_PROMPT, identity_line, category_prompt, "Preserve the confirmed category exactly."))


def build_master_negative_prompt(identity: Mapping[str, object]) -> str:
    category = str(identity.get("category", "other"))
    return CATEGORY_NEGATIVE_PROMPTS.get(category, CATEGORY_NEGATIVE_PROMPTS["other"])

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
    PoseOption("listening_focus", "listening", "Gesto de escuta", "clear listening response adapted to the subject's confirmed anatomy; never invent a human hand for an animal or object"),
    PoseOption("listening_process", "listening", "Inclinado para ouvir", "leaning the upper body slightly toward the sound with attentive eyes"),
    PoseOption("listening_natural", "listening", "Reação natural", "natural listening reaction using gaze, head, ears, wings, posture, or object affordances appropriate to the confirmed subject"),
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


def build_pose_prompt(identity: Mapping[str, object], role: str, option: PoseOption) -> str:
    category = str(identity.get("category", "other"))
    label = str(identity.get("label", "confirmed subject"))
    species = str(identity.get("species") or "").strip()
    category_detail = f"category {category}"
    if species:
        category_detail += f", species {species}"
    return (
        f"{POSE_PROMPT} The confirmed subject is {label} ({category_detail}). "
        f"Runtime role: {role}. Requested pose: {option.instruction}. "
        "Use only the approved Master as visual identity reference."
    )


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

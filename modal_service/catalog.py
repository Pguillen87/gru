"""Versioned prompts and pose catalog shared by the Web v2 pipeline."""

from __future__ import annotations

from dataclasses import dataclass

MASTER_PROMPT_VERSION = "master-v4"
POSE_PROMPT_VERSION = "pose-worker-v1"
POSE_CATALOG_VERSION = "web-poses-v1"
POSE_TEMPLATE_VERSION = "web-poses-v1"

_MASTER_BASE = (
    "Create one clean, friendly, full-body 2D editorial cartoon mascot from the supplied reference. "
    "Preserve only identity traits, colors, clothing and marks that are clearly visible. "
    "Do not invent tattoos, scars, bruises, patches, body markings, accessories or anatomy in unseen areas. "
    "Use clean, uniform anatomy for occluded body areas. Single centered character with a strong silhouette. "
    "Render on a perfectly uniform light neutral chroma background for later segmentation. "
    "No ground shadow, text, watermark, frame, checkerboard, texture, scenery or extra subject."
)

_IDENTITY_RULES = {
    "human": (
        "The subject is HUMAN. Keep entirely human anatomy and skin: ordinary human ears, hands, feet and limbs. "
        "Never add fur, feathers, muzzle, paws, tail, horns, animal ears, hybrid traits, bruises or invented skin marks."
    ),
    "animal": (
        "The subject is an ANIMAL. Preserve the confirmed species and its natural anatomy, coat or feather colors, "
        "markings and body plan. Never turn it into another species or a human-animal hybrid."
    ),
    "object": (
        "The subject is an OBJECT. Preserve its recognizable materials, construction, proportions and essential parts. "
        "Do not add biological anatomy unless it is a simple cartoon facial expression requested by the product."
    ),
    "other": (
        "Preserve exactly the confirmed subject description and its recognizable structure. "
        "Do not infer unrelated anatomy, species traits or accessories."
    ),
}


def build_master_prompt(subject_identity: dict[str, object] | None) -> str:
    """Build the immutable master-v4 prompt from a confirmed identity."""
    identity = subject_identity or {}
    category = str(identity.get("category", "other")).strip().lower()
    rule = _IDENTITY_RULES.get(category, _IDENTITY_RULES["other"])
    label = str(identity.get("label", "")).strip()[:80]
    species = str(identity.get("species", "")).strip()[:80]
    confirmed = "confirmed" if identity.get("confirmed") is True else "unconfirmed"
    context = f"Subject classification: {category} ({confirmed})."
    if label:
        context += f" User label: {label}."
    if species:
        context += f" Confirmed species: {species}."
    return " ".join((_MASTER_BASE, context, rule))


def build_pose_prompt(subject_identity: dict[str, object] | None, instruction: str) -> str:
    """Build a pose prompt which treats the approved Master as the sole identity source."""
    identity_rule = _IDENTITY_RULES.get(
        str((subject_identity or {}).get("category", "other")).lower(), _IDENTITY_RULES["other"]
    )
    return " ".join((
        "Edit the approved GRU Master using the pose reference only for posture and gesture.", identity_rule,
        "Preserve face, clothing, colors, proportions and illustration style exactly.", instruction,
        "Single centered character on a uniform light neutral chroma background. No ground shadow, text, frame, "
        "checkerboard, scenery, invented marks or extra objects.",
    ))


# Compatibility exports used by V1 documentation and regression tests.
MASTER_PROMPT = build_master_prompt(None)
POSE_PROMPT = build_pose_prompt(None, "Use the requested operational pose.")


@dataclass(frozen=True)
class PoseTemplate:
    role: str
    option_id: str
    template_id: str
    name: str
    instruction: str
    asset_key: str


POSES = (
    PoseTemplate("normal", "normal_attentive", "normal_attentive", "Pronto e atento", "Balanced upright posture and attentive expression.", "references/normal_attentive.png"),
    PoseTemplate("normal", "normal_relaxed", "normal_relaxed", "Relaxado", "Relaxed natural posture with a calm expression.", "references/normal_relaxed.png"),
    PoseTemplate("normal", "normal_curious", "normal_curious", "Observador", "Curious observing posture while preserving the silhouette.", "references/normal_curious.png"),
    PoseTemplate("normal", "normal_firm", "normal_firm", "Sereno", "Calm, confident waiting posture.", "references/normal_firm.png"),
    PoseTemplate("listening", "listening_focus", "listening_focus", "Gesto de escuta", "Clear listening gesture adapted to the subject anatomy.", "references/listening_focus.png"),
    PoseTemplate("listening", "listening_process", "listening_process", "Inclinado para ouvir", "Body slightly oriented toward a sound source.", "references/listening_process.png"),
    PoseTemplate("listening", "listening_natural", "listening_natural", "Reação natural", "Natural listening reaction using only anatomically valid parts.", "references/listening_natural.png"),
    PoseTemplate("listening", "listening_ready", "listening_ready", "Cabeça inclinada", "Focused head tilt or equivalent anatomical listening cue.", "references/listening_ready.png"),
    PoseTemplate("transcribing", "transcribing_notes", "transcribing_notes", "Anotando", "Simple note-taking action with one compact support object when needed.", "references/transcribing_notes.png"),
    PoseTemplate("transcribing", "transcribing_fast", "transcribing_fast", "Digitando", "Focused typing action with a compact device.", "references/transcribing_fast.png"),
    PoseTemplate("transcribing", "transcribing_thought", "transcribing_thought", "Organizando ideias", "Attentive processing pose without excessive accessories.", "references/transcribing_thought.png"),
    PoseTemplate("transcribing", "transcribing_active", "transcribing_active", "Processando", "Clear active gesture representing speech becoming written content.", "references/transcribing_active.png"),
)

POSE_BY_OPTION = {pose.option_id: pose for pose in POSES}
POSE_CATALOG = {role: [pose.option_id for pose in POSES if pose.role == role] for role in ("normal", "listening", "transcribing")}


def validate_pose_choices(choices: dict[str, str]) -> tuple[PoseTemplate, PoseTemplate, PoseTemplate]:
    if set(choices) != set(POSE_CATALOG):
        raise ValueError("Exactly one option is required for every pose role.")
    selected: list[PoseTemplate] = []
    for role in ("normal", "listening", "transcribing"):
        option_id = choices[role]
        pose = POSE_BY_OPTION.get(option_id)
        if pose is None or pose.role != role:
            raise ValueError(f"Pose option {option_id!r} is invalid for {role}.")
        selected.append(pose)
    return selected[0], selected[1], selected[2]


def consistency_templates() -> tuple[PoseTemplate, PoseTemplate, PoseTemplate]:
    return POSES[0], POSES[4], POSES[8]


def mvp_templates() -> tuple[PoseTemplate, ...]:
    return POSES[:6]

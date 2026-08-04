"""Versioned pose and prompt catalog. Image assets are intentionally external."""

from __future__ import annotations

from dataclasses import dataclass


MASTER_PROMPT_VERSION = "master-v2"
POSE_PROMPT_VERSION = "pose-v2"
POSE_TEMPLATE_VERSION = "poses-v1"

MASTER_PROMPT = (
    "Create a clean, friendly, full-body 2D cartoon mascot from the supplied reference photo. "
    "First identify the primary subject and preserve its category exactly: a human remains a human; "
    "an animal remains its exact species. Preserve the subject's distinctive identity, natural anatomy, "
    "colors, markings, facial proportions, and visible clothing when present. "
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
    "Apply only the posture and expression shown by the pose reference. Single character, clean anatomy, "
    "transparent background when supported, no text, watermark, or extra objects."
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

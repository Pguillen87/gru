"""Versioned pose and prompt catalog. Image assets are intentionally external."""

from __future__ import annotations

from dataclasses import dataclass


MASTER_PROMPT_VERSION = "master-v1"
POSE_PROMPT_VERSION = "pose-v1"
POSE_TEMPLATE_VERSION = "poses-v1"

MASTER_PROMPT = (
    "Create a clean, friendly 2D cartoon mascot from the supplied pet photo. "
    "Preserve coat colors, markings, eye shape, ears, facial proportions, and identity. "
    "Single centered character, clear silhouette for small Android sizes, neutral background, "
    "no text, no watermark, no accessories, no extra animals."
)

POSE_PROMPT = (
    "Preserve exactly the same GRU mascot identity from the master reference: same coat markings, "
    "colors, eyes, ears, facial proportions, and graphic style. Apply only the posture and expression "
    "shown by the pose reference. Single character, clean anatomy, no text, watermark, or extra objects."
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

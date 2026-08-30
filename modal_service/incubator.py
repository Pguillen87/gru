"""CPU-only decisions and product projection for asynchronous incubations.

This module never schedules GPU work. It ranks already-persisted Master
derivatives and derives stable product states from the durable JobRecord.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from io import BytesIO
from math import sqrt
from pathlib import Path
from typing import Protocol

from modal_service.domain import JobRecord, JobState, WorkflowMode


RANKER_VERSION = "master-ranker-v1"
SUBJECT_HINT_VERSION = "subject-hint-v1"
REQUIRED_MASTER_IDS = ("master_1", "master_2", "master_3")
VISUAL_ENCODER_VERSION = "subject-encoder-v1"
_CATEGORY_ORDER = ("human", "animal", "object", "other")


class VisualFeatureEncoder(Protocol):
    version: str

    def encode(self, image: bytes) -> tuple[float, ...]: ...

    def category_scores(self, image: bytes) -> dict[str, float]: ...


class PillowFeatureEncoder:
    """Deterministic CPU fallback used when the pinned semantic encoder is unavailable.

    It provides identity/composition features only. Category scores deliberately
    remain neutral, so this fallback can never manufacture a mismatch warning.
    """

    version = "pillow-visual-features-v1"

    def encode(self, image: bytes) -> tuple[float, ...]:
        from io import BytesIO
        from PIL import Image, ImageStat

        with Image.open(BytesIO(image)) as source:
            rgba = source.convert("RGBA").resize((32, 32))
            stat = ImageStat.Stat(rgba)
            means = tuple(value / 255.0 for value in stat.mean)
            deviations = tuple(value / 255.0 for value in stat.stddev)
            histogram = rgba.convert("RGB").histogram()
            buckets = tuple(sum(histogram[index:index + 32]) / (32 * 32 * 3) for index in range(0, 768, 32))
            return means + deviations + buckets

    def category_scores(self, image: bytes) -> dict[str, float]:
        del image
        return {"human": 0.75, "animal": 0.75, "object": 0.75, "other": 0.75}


class VisualEncoderUnavailable(RuntimeError):
    """The pinned semantic encoder is unavailable or fails integrity checks."""


class PinnedTorchScriptVisualEncoder:
    """CPU encoder loaded only from a checksum-pinned local artifact.

    The artifact contract is deliberately narrow: a TorchScript module accepts
    an RGB tensor `[1, 3, 224, 224]` and returns either `(embedding, logits)`
    or `{"embedding": ..., "logits": ...}`. It is never downloaded during a
    request, so an unavailable model degrades the optional hint and blocks the
    automatic ranker rather than silently changing its quality bar.
    """

    version = VISUAL_ENCODER_VERSION

    def __init__(self, checkpoint: Path, expected_sha256: str) -> None:
        if not checkpoint.is_file():
            raise VisualEncoderUnavailable("VISUAL_ENCODER_NOT_READY")
        actual = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
        if actual != expected_sha256.lower():
            raise VisualEncoderUnavailable("VISUAL_ENCODER_CHECKSUM_INVALID")
        try:
            import torch
        except ImportError as error:
            raise VisualEncoderUnavailable("VISUAL_ENCODER_RUNTIME_UNAVAILABLE") from error
        self._torch = torch
        self._model = torch.jit.load(str(checkpoint), map_location="cpu").eval()

    def _output(self, image: bytes) -> tuple[tuple[float, ...], dict[str, float]]:
        from PIL import Image

        with Image.open(BytesIO(image)) as source:
            rgb = source.convert("RGB").resize((224, 224))
            values = self._torch.tensor(list(rgb.getdata()), dtype=self._torch.float32)
        tensor = values.reshape(224, 224, 3).permute(2, 0, 1).unsqueeze(0) / 255.0
        with self._torch.inference_mode():
            output = self._model(tensor)
        if isinstance(output, dict):
            embedding, logits = output.get("embedding"), output.get("logits")
        else:
            embedding, logits = output
        if embedding is None or logits is None:
            raise VisualEncoderUnavailable("VISUAL_ENCODER_OUTPUT_INVALID")
        vector = tuple(float(value) for value in embedding.flatten().tolist())
        probabilities = self._torch.softmax(logits.flatten(), dim=0).tolist()
        if len(probabilities) != len(_CATEGORY_ORDER) or not vector:
            raise VisualEncoderUnavailable("VISUAL_ENCODER_OUTPUT_INVALID")
        return vector, dict(zip(_CATEGORY_ORDER, (float(value) for value in probabilities), strict=True))

    def encode(self, image: bytes) -> tuple[float, ...]:
        return self._output(image)[0]

    def category_scores(self, image: bytes) -> dict[str, float]:
        return self._output(image)[1]


def load_pinned_visual_encoder() -> PinnedTorchScriptVisualEncoder:
    checkpoint = os.getenv("INCUBATOR_VISUAL_ENCODER_PATH", "").strip()
    checksum = os.getenv("INCUBATOR_VISUAL_ENCODER_SHA256", "").strip().lower()
    if not checkpoint or len(checksum) != 64 or any(char not in "0123456789abcdef" for char in checksum):
        raise VisualEncoderUnavailable("VISUAL_ENCODER_NOT_CONFIGURED")
    return PinnedTorchScriptVisualEncoder(Path(checkpoint), checksum)


def pinned_encoder_status() -> dict[str, object]:
    try:
        encoder = load_pinned_visual_encoder()
    except VisualEncoderUnavailable as error:
        return {"ready": False, "reasonCode": str(error), "version": VISUAL_ENCODER_VERSION}
    return {"ready": True, "reasonCode": None, "version": encoder.version}


@dataclass(frozen=True)
class RankedMaster:
    master_id: str
    identity: float
    category: float
    composition: float

    @property
    def total(self) -> float:
        return round(self.identity * 0.50 + self.category * 0.30 + self.composition * 0.20, 6)


def cosine_similarity(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    if not left or len(left) != len(right):
        return 0.0
    denominator = sqrt(sum(value * value for value in left)) * sqrt(sum(value * value for value in right))
    if denominator == 0:
        return 0.0
    return max(0.0, min(1.0, sum(a * b for a, b in zip(left, right, strict=True)) / denominator))


def subject_hint(selected_category: str, scores: dict[str, float] | None) -> dict[str, object]:
    if not scores:
        return {
            "version": SUBJECT_HINT_VERSION,
            "suggestedCategory": "uncertain",
            "confidenceBand": "low",
            "requiresConfirmation": False,
            "overrideConfirmed": False,
        }
    ordered = sorted(((key, float(value)) for key, value in scores.items() if key in {"human", "animal"}), key=lambda item: (-item[1], item[0]))
    if len(ordered) < 2:
        return subject_hint(selected_category, None)
    suggested, confidence = ordered[0]
    margin = confidence - ordered[1][1]
    high = confidence >= 0.78 and margin >= 0.18
    return {
        "version": SUBJECT_HINT_VERSION,
        "suggestedCategory": suggested if high else "uncertain",
        "confidenceBand": "high" if high else "medium" if confidence >= 0.60 else "low",
        "requiresConfirmation": high and suggested != selected_category and selected_category in {"human", "animal"},
        "overrideConfirmed": False,
    }


def rank_masters(
    source: bytes,
    candidates: dict[str, bytes],
    qc_by_master: dict[str, dict[str, object]],
    subject_category: str,
    encoder: VisualFeatureEncoder,
) -> dict[str, object]:
    if tuple(sorted(candidates)) != REQUIRED_MASTER_IDS:
        raise ValueError("Master ranking requires exactly three candidates.")
    source_features = encoder.encode(source)
    ranked: list[RankedMaster] = []
    for master_id in REQUIRED_MASTER_IDS:
        qc = qc_by_master.get(master_id) or {}
        if qc.get("status") != "passed":
            continue
        image = candidates[master_id]
        category_scores = encoder.category_scores(image)
        category = float(category_scores.get(subject_category, 0.0))
        alpha_ratio = float(qc.get("alpha_ratio", 0.0))
        border_ratio = float(qc.get("border_opaque_ratio", 1.0))
        components = int(qc.get("component_count", qc.get("foreground_components", 100)))
        composition = max(0.0, min(1.0, 1.0 - border_ratio - max(0.0, alpha_ratio - 0.78) - max(0, components - 4) * 0.04))
        ranked.append(RankedMaster(
            master_id,
            cosine_similarity(source_features, encoder.encode(image)),
            max(0.0, min(1.0, category)),
            composition,
        ))
    eligible = [item for item in ranked if item.identity >= 0.55 and item.category >= 0.50 and item.composition >= 0.55]
    if not eligible:
        raise ValueError("No Master candidate passed automatic ranking gates.")
    winner = sorted(eligible, key=lambda item: (-item.total, item.master_id))[0]
    return {
        "rankerVersion": RANKER_VERSION,
        "selectedMasterId": winner.master_id,
        "scores": [
            {
                "masterId": item.master_id,
                "identity": round(item.identity, 6),
                "category": round(item.category, 6),
                "composition": round(item.composition, 6),
                "total": item.total,
            }
            for item in sorted(ranked, key=lambda item: item.master_id)
        ],
    }


def product_state(job: JobRecord) -> str:
    if job.state in {JobState.FAILED, JobState.CANCELED}:
        return "FAILED"
    if job.generation_ready_at or job.state is JobState.COMPLETED:
        return "READY_TO_HATCH"
    if job.state in {JobState.REGISTERED, JobState.QUEUED, JobState.VALIDATING_INPUT, JobState.READY_FOR_GENERATION}:
        return "PREPARING"
    return "INCUBATING"


def is_async_incubation(job: JobRecord) -> bool:
    return job.workflow_mode == WorkflowMode.ASYNC_INCUBATOR_V1.value

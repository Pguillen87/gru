"""CPU-only visual decisions for asynchronous incubations.

This module intentionally has no Modal or GPU dependency. The product sees a
small ``VisualFeatureEncoder`` interface; ONNX Runtime is an implementation
detail confined to the verified SigLIP adapter.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from io import BytesIO
from math import exp, sqrt
from pathlib import Path
from typing import Any, Protocol

from modal_service.domain import JobRecord, JobState, WorkflowMode


ENCODER_VERSION = "siglip-base-p16-224-zeroshot-v1"
SUBJECT_HINT_POLICY_VERSION = "subject-hint-policy-v2"
MASTER_RANKER_VERSION = "master-ranker-v2"
ARTIFACT_PACKAGE_NAME = "siglip-base-p16-224-zeroshot-v1"
ARTIFACT_SCHEMA_VERSION = 1
UPSTREAM_MODEL_ID = "google/siglip-base-patch16-224"
UPSTREAM_REVISION = "7fd15f0689c79d79e38b1c2e2e2370a7bf2761ed"
UPSTREAM_WEIGHTS_SHA256 = "2c63cb7d1f2e95ba501893cbb8faeb4ea9a3af295498d35097126228659c2af8"
REQUIRED_MASTER_IDS = ("master_1", "master_2", "master_3")
CATEGORY_ORDER = ("human", "animal", "object", "other")
EXPECTED_PREPROCESS = {
    "colorSpace": "RGB",
    "resize": {"height": 224, "width": 224, "resample": "bicubic"},
    "rescale": 1.0 / 255.0,
    "normalize": {"mean": [0.5, 0.5, 0.5], "std": [0.5, 0.5, 0.5]},
}


class VisualEncoderUnavailable(RuntimeError):
    """A semantic visual encoder was not safely available."""


class VisualFeatureEncoder(Protocol):
    """Stable product-facing interface for a local visual encoder."""

    version: str

    def encode(self, image: bytes) -> tuple[float, ...]: ...

    def classify(self, image: bytes) -> dict[str, float]: ...

    def provenance(self) -> dict[str, str]: ...


@dataclass(frozen=True)
class EncoderManifest:
    encoder_version: str
    subject_hint_policy_version: str
    master_ranker_version: str
    onnxruntime_version: str
    upstream_model_id: str
    upstream_revision: str
    upstream_weights_sha256: str
    files: dict[str, str]
    prompts: tuple[str, ...]
    prompt_categories: tuple[int, ...]
    embedding_dimension: int
    logit_scale: float
    logit_bias: float
    preprocess: dict[str, Any]
    thresholds: dict[str, float]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _require_string(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise VisualEncoderUnavailable("VISUAL_ENCODER_MANIFEST_INVALID")
    return value


def _require_sha(value: str) -> str:
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value.lower()):
        raise VisualEncoderUnavailable("VISUAL_ENCODER_MANIFEST_INVALID")
    return value.lower()


def prompt_contract_sha256(prompts: list[str] | tuple[str, ...], categories: list[int] | tuple[int, ...]) -> str:
    payload = {"prompts": list(prompts), "promptCategoryIndices": list(categories), "categoryOrder": list(CATEGORY_ORDER)}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _manifest_from_json(payload: dict[str, Any]) -> EncoderManifest:
    if payload.get("schemaVersion") != ARTIFACT_SCHEMA_VERSION:
        raise VisualEncoderUnavailable("VISUAL_ENCODER_MANIFEST_INVALID")
    artifact, upstream, runtime = payload.get("artifact"), payload.get("upstream"), payload.get("runtime")
    contract, mathematics, policy, files = payload.get("contract"), payload.get("mathematics"), payload.get("policy"), payload.get("files")
    if not all(isinstance(item, dict) for item in (artifact, upstream, runtime, contract, mathematics, policy, files)):
        raise VisualEncoderUnavailable("VISUAL_ENCODER_MANIFEST_INVALID")
    if artifact.get("package") != ARTIFACT_PACKAGE_NAME or tuple(contract.get("categoryOrder", ())) != CATEGORY_ORDER:
        raise VisualEncoderUnavailable("VISUAL_ENCODER_MANIFEST_INVALID")
    if artifact.get("encoderVersion") != ENCODER_VERSION:
        raise VisualEncoderUnavailable("VISUAL_ENCODER_MANIFEST_INVALID")
    if policy.get("subjectHintPolicyVersion") != SUBJECT_HINT_POLICY_VERSION:
        raise VisualEncoderUnavailable("VISUAL_ENCODER_MANIFEST_INVALID")
    if policy.get("masterRankerVersion") != MASTER_RANKER_VERSION:
        raise VisualEncoderUnavailable("VISUAL_ENCODER_MANIFEST_INVALID")
    if upstream.get("modelId") != UPSTREAM_MODEL_ID or upstream.get("revision") != UPSTREAM_REVISION:
        raise VisualEncoderUnavailable("VISUAL_ENCODER_MANIFEST_INVALID")
    if upstream.get("weightsSha256") != UPSTREAM_WEIGHTS_SHA256:
        raise VisualEncoderUnavailable("VISUAL_ENCODER_MANIFEST_INVALID")
    if runtime.get("providers") != ["CPUExecutionProvider"]:
        raise VisualEncoderUnavailable("VISUAL_ENCODER_MANIFEST_INVALID")
    if contract.get("inputShape") != [1, 3, 224, 224] or contract.get("embeddingDimension") != 768:
        raise VisualEncoderUnavailable("VISUAL_ENCODER_MANIFEST_INVALID")
    if mathematics.get("embeddingNormalization") != "l2" or mathematics.get("prototypeNormalization") != "l2":
        raise VisualEncoderUnavailable("VISUAL_ENCODER_MANIFEST_INVALID")
    if mathematics.get("similarity") != "normalized_dot_product" or mathematics.get("promptAggregation") != "mean_logit_per_category_then_softmax":
        raise VisualEncoderUnavailable("VISUAL_ENCODER_MANIFEST_INVALID")
    prompts, category_indices = mathematics.get("prompts"), mathematics.get("promptCategoryIndices")
    if not isinstance(prompts, list) or not prompts or not isinstance(category_indices, list) or len(prompts) != len(category_indices):
        raise VisualEncoderUnavailable("VISUAL_ENCODER_MANIFEST_INVALID")
    if any(not isinstance(prompt, str) or not prompt for prompt in prompts) or any(index not in range(4) for index in category_indices):
        raise VisualEncoderUnavailable("VISUAL_ENCODER_MANIFEST_INVALID")
    if mathematics.get("promptsSha256") != prompt_contract_sha256(prompts, category_indices):
        raise VisualEncoderUnavailable("VISUAL_ENCODER_MANIFEST_INVALID")
    if not all(isinstance(name, str) and isinstance(value, str) for name, value in files.items()):
        raise VisualEncoderUnavailable("VISUAL_ENCODER_MANIFEST_INVALID")
    verified_files = {name: _require_sha(value) for name, value in files.items()}
    if set(verified_files) != {"vision_encoder.onnx", "text_prototypes.npz"}:
        raise VisualEncoderUnavailable("VISUAL_ENCODER_MANIFEST_INVALID")
    thresholds = policy.get("thresholds")
    if not isinstance(thresholds, dict) or not all(isinstance(value, (float, int)) for value in thresholds.values()):
        raise VisualEncoderUnavailable("VISUAL_ENCODER_MANIFEST_INVALID")
    try:
        logit_scale, logit_bias = float(mathematics.get("logitScale")), float(mathematics.get("logitBias"))
    except (TypeError, ValueError) as error:
        raise VisualEncoderUnavailable("VISUAL_ENCODER_MANIFEST_INVALID") from error
    if mathematics.get("preprocess") != EXPECTED_PREPROCESS:
        raise VisualEncoderUnavailable("VISUAL_ENCODER_MANIFEST_INVALID")
    return EncoderManifest(
        encoder_version=_require_string(artifact, "encoderVersion"),
        subject_hint_policy_version=_require_string(policy, "subjectHintPolicyVersion"),
        master_ranker_version=_require_string(policy, "masterRankerVersion"),
        onnxruntime_version=_require_string(runtime, "onnxruntimeVersion"),
        upstream_model_id=_require_string(upstream, "modelId"),
        upstream_revision=_require_string(upstream, "revision"),
        upstream_weights_sha256=_require_sha(_require_string(upstream, "weightsSha256")),
        files=verified_files,
        prompts=tuple(prompts),
        prompt_categories=tuple(int(index) for index in category_indices),
        embedding_dimension=768,
        logit_scale=logit_scale,
        logit_bias=logit_bias,
        preprocess=dict(EXPECTED_PREPROCESS),
        thresholds={key: float(value) for key, value in thresholds.items()},
    )


def _load_manifest(package_dir: Path) -> EncoderManifest:
    try:
        payload = json.loads((package_dir / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise VisualEncoderUnavailable("VISUAL_ENCODER_MANIFEST_INVALID") from error
    if not isinstance(payload, dict):
        raise VisualEncoderUnavailable("VISUAL_ENCODER_MANIFEST_INVALID")
    manifest = _manifest_from_json(payload)
    for filename, expected in manifest.files.items():
        candidate = package_dir / filename
        if not candidate.is_file():
            raise VisualEncoderUnavailable("VISUAL_ENCODER_NOT_READY")
        if _sha256(candidate) != expected:
            raise VisualEncoderUnavailable("VISUAL_ENCODER_CHECKSUM_INVALID")
    return manifest


def _normalise(vector: Any) -> Any:
    norm = float((vector * vector).sum()) ** 0.5
    if norm <= 0:
        raise VisualEncoderUnavailable("VISUAL_ENCODER_OUTPUT_INVALID")
    return vector / norm


class SiglipOnnxVisualEncoder:
    """Verified, CPU-only SigLIP vision adapter.

    Text features are generated offline from pinned prompts and loaded as a
    checksummed data file. Requests never download a model or call a third
    party. The rest of the product depends only on ``VisualFeatureEncoder``.
    """

    def __init__(self, package_dir: Path) -> None:
        self._manifest = _load_manifest(package_dir)
        try:
            import numpy as np
            import onnxruntime as ort
        except ImportError as error:
            raise VisualEncoderUnavailable("VISUAL_ENCODER_RUNTIME_UNAVAILABLE") from error
        if ort.__version__ != self._manifest.onnxruntime_version:
            raise VisualEncoderUnavailable("VISUAL_ENCODER_RUNTIME_INCOMPATIBLE")
        try:
            self._session = ort.InferenceSession(str(package_dir / "vision_encoder.onnx"), providers=["CPUExecutionProvider"])
        except Exception as error:
            raise VisualEncoderUnavailable("VISUAL_ENCODER_RUNTIME_INCOMPATIBLE") from error
        if tuple(self._session.get_providers()) != ("CPUExecutionProvider",):
            raise VisualEncoderUnavailable("VISUAL_ENCODER_PROVIDER_INVALID")
        inputs, outputs = self._session.get_inputs(), self._session.get_outputs()
        if (
            len(inputs) != 1
            or len(outputs) != 1
            or tuple(inputs[0].shape) != (1, 3, 224, 224)
            or tuple(outputs[0].shape) != (1, self._manifest.embedding_dimension)
        ):
            raise VisualEncoderUnavailable("VISUAL_ENCODER_OUTPUT_INVALID")
        self._input_name, self._output_name = inputs[0].name, outputs[0].name
        try:
            prototypes = np.load(package_dir / "text_prototypes.npz", allow_pickle=False)["embeddings"]
        except Exception as error:
            raise VisualEncoderUnavailable("VISUAL_ENCODER_PROTOTYPES_INVALID") from error
        if prototypes.dtype != np.float32 or prototypes.shape != (len(self._manifest.prompts), self._manifest.embedding_dimension):
            raise VisualEncoderUnavailable("VISUAL_ENCODER_PROTOTYPES_INVALID")
        self._np = np
        self._prototypes = np.stack([_normalise(vector.astype(np.float32, copy=False)) for vector in prototypes])
        self.version = self._manifest.encoder_version

    def provenance(self) -> dict[str, str]:
        return {
            "encoderVersion": self._manifest.encoder_version,
            "subjectHintPolicyVersion": self._manifest.subject_hint_policy_version,
            "masterRankerVersion": self._manifest.master_ranker_version,
            "upstreamModelId": self._manifest.upstream_model_id,
            "upstreamRevision": self._manifest.upstream_revision,
        }

    def _tensor(self, image: bytes) -> Any:
        from PIL import Image

        with Image.open(BytesIO(image)) as source:
            rgb = source.convert("RGB").resize((224, 224), Image.Resampling.BICUBIC)
            values = self._np.asarray(rgb, dtype=self._np.float32) / 255.0
        values = (values - 0.5) / 0.5
        return self._np.ascontiguousarray(values.transpose(2, 0, 1)[None, ...], dtype=self._np.float32)

    def _embedding(self, image: bytes) -> Any:
        try:
            output = self._session.run([self._output_name], {self._input_name: self._tensor(image)})[0]
        except Exception as error:
            raise VisualEncoderUnavailable("VISUAL_ENCODER_RUNTIME_FAILED") from error
        if getattr(output, "dtype", None) != self._np.float32 or getattr(output, "shape", None) != (1, self._manifest.embedding_dimension):
            raise VisualEncoderUnavailable("VISUAL_ENCODER_OUTPUT_INVALID")
        return _normalise(output[0])

    def encode(self, image: bytes) -> tuple[float, ...]:
        return tuple(float(value) for value in self._embedding(image).tolist())

    def classify(self, image: bytes) -> dict[str, float]:
        embedding = self._embedding(image)
        per_prompt = embedding @ self._prototypes.T
        logits = []
        for category_index in range(4):
            values = [float(per_prompt[index]) * self._manifest.logit_scale + self._manifest.logit_bias
                      for index, actual in enumerate(self._manifest.prompt_categories) if actual == category_index]
            if not values:
                raise VisualEncoderUnavailable("VISUAL_ENCODER_PROTOTYPES_INVALID")
            logits.append(sum(values) / len(values))
        maximum = max(logits)
        weights = [exp(value - maximum) for value in logits]
        total = sum(weights)
        if total <= 0:
            raise VisualEncoderUnavailable("VISUAL_ENCODER_OUTPUT_INVALID")
        return dict(zip(CATEGORY_ORDER, (weight / total for weight in weights), strict=True))


class NeutralVisualEncoder:
    """Non-semantic fallback for the optional subject hint only."""

    version = "neutral-visual-encoder-v1"

    def encode(self, image: bytes) -> tuple[float, ...]:
        del image
        raise VisualEncoderUnavailable("VISUAL_ENCODER_NOT_READY")

    def classify(self, image: bytes) -> dict[str, float]:
        del image
        return dict(zip(CATEGORY_ORDER, (0.25, 0.25, 0.25, 0.25), strict=True))

    def provenance(self) -> dict[str, str]:
        return {"encoderVersion": self.version}


def load_pinned_visual_encoder() -> VisualFeatureEncoder:
    configured = os.getenv("INCUBATOR_VISUAL_ENCODER_DIR", "").strip()
    if not configured:
        raise VisualEncoderUnavailable("VISUAL_ENCODER_NOT_CONFIGURED")
    package_dir = Path(configured)
    if package_dir.name != ARTIFACT_PACKAGE_NAME:
        raise VisualEncoderUnavailable("VISUAL_ENCODER_MANIFEST_INVALID")
    return SiglipOnnxVisualEncoder(package_dir)


def pinned_encoder_status() -> dict[str, object]:
    try:
        encoder = load_pinned_visual_encoder()
    except VisualEncoderUnavailable as error:
        return {
            "ready": False,
            "reasonCode": str(error),
            "encoderVersion": ENCODER_VERSION,
            "subjectHintPolicyVersion": SUBJECT_HINT_POLICY_VERSION,
            "masterRankerVersion": MASTER_RANKER_VERSION,
        }
    return {"ready": True, "reasonCode": None, **encoder.provenance()}


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
        return {"version": SUBJECT_HINT_POLICY_VERSION, "suggestedCategory": "uncertain", "confidenceBand": "low", "requiresConfirmation": False, "overrideConfirmed": False}
    ordered = sorted(((key, float(value)) for key, value in scores.items() if key in {"human", "animal"}), key=lambda item: (-item[1], item[0]))
    if len(ordered) < 2:
        return subject_hint(selected_category, None)
    suggested, confidence = ordered[0]
    margin = confidence - ordered[1][1]
    high = confidence >= 0.78 and margin >= 0.18
    return {
        "version": SUBJECT_HINT_POLICY_VERSION,
        "suggestedCategory": suggested if high else "uncertain",
        "confidenceBand": "high" if high else "medium" if confidence >= 0.60 else "low",
        "requiresConfirmation": high and suggested != selected_category and selected_category in {"human", "animal"},
        "overrideConfirmed": False,
    }


def rank_masters(source: bytes, candidates: dict[str, bytes], qc_by_master: dict[str, dict[str, object]], subject_category: str, encoder: VisualFeatureEncoder) -> dict[str, object]:
    if tuple(sorted(candidates)) != REQUIRED_MASTER_IDS:
        raise ValueError("Master ranking requires exactly three candidates.")
    source_features = encoder.encode(source)
    ranked: list[RankedMaster] = []
    for master_id in REQUIRED_MASTER_IDS:
        qc = qc_by_master.get(master_id) or {}
        if qc.get("status") != "passed":
            continue
        image = candidates[master_id]
        category = float(encoder.classify(image).get(subject_category, 0.0))
        alpha_ratio, border_ratio = float(qc.get("alpha_ratio", 0.0)), float(qc.get("border_opaque_ratio", 1.0))
        components = int(qc.get("component_count", qc.get("foreground_components", 100)))
        composition = max(0.0, min(1.0, 1.0 - border_ratio - max(0.0, alpha_ratio - 0.78) - max(0, components - 4) * 0.04))
        ranked.append(RankedMaster(master_id, cosine_similarity(source_features, encoder.encode(image)), max(0.0, min(1.0, category)), composition))
    eligible = [item for item in ranked if item.identity >= 0.55 and item.category >= 0.50 and item.composition >= 0.55]
    if not eligible:
        raise ValueError("No Master candidate passed automatic ranking gates.")
    winner = sorted(eligible, key=lambda item: (-item.total, item.master_id))[0]
    return {
        "encoderVersion": encoder.version,
        "masterRankerVersion": MASTER_RANKER_VERSION,
        "selectedMasterId": winner.master_id,
        "scores": [{"masterId": item.master_id, "identity": round(item.identity, 6), "category": round(item.category, 6), "composition": round(item.composition, 6), "total": item.total} for item in sorted(ranked, key=lambda item: item.master_id)],
    }


def shadow_ranking_observation(selection: dict[str, object]) -> dict[str, object]:
    """Return aggregate, non-image observations; never an embedding."""
    scores = selection.get("scores")
    if not isinstance(scores, list):
        raise ValueError("Shadow ranking selection is invalid.")
    return {
        "encoderVersion": selection.get("encoderVersion"),
        "masterRankerVersion": selection.get("masterRankerVersion"),
        "candidateCount": len(scores),
        "winner": selection.get("selectedMasterId"),
        "highestScore": max((float(item.get("total", 0.0)) for item in scores if isinstance(item, dict)), default=0.0),
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

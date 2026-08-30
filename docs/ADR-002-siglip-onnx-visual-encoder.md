# ADR-002: SigLIP ONNX visual encoder for Incubator observation

## Status

Accepted for code review only. The artifact is not provisioned and this ADR
does not authorize a Modal deployment, Incubator enablement, GPU work, or
automatic Master selection.

## Decision

Use a local, CPU-only ONNX Runtime adapter for
`google/siglip-base-patch16-224` at revision
`7fd15f0689c79d79e38b1c2e2e2370a7bf2761ed`. The model card declares
Apache-2.0; the controlled exporter records that declaration, the upstream
weight SHA-256 actually used, and all generated artifact hashes. Legal review
of the exported artifact remains a release requirement.

The approved upstream input is `model.safetensors` with SHA-256
`2c63cb7d1f2e95ba501893cbb8faeb4ea9a3af295498d35097126228659c2af8`
(812,672,320 bytes). A different weight file is rejected before export and at
runtime through the manifest contract.

The package is named `siglip-base-p16-224-zeroshot-v1` and contains only:

- `vision_encoder.onnx`;
- `text_prototypes.npz`;
- `manifest.json`.

It lives in the isolated Modal model Volume, never in Git. Requests do not
download models, send images to another service, or persist embeddings.

## Mathematical contract

The manifest freezes RGB/BICUBIC 224 preprocessing, `x / 255`, mean/std
`(0.5, 0.5, 0.5)`, L2 normalization of image and text vectors, normalized dot
product, SigLIP logit scale/bias, all prompt strings, prompt/category mapping,
the `mean_logit_per_category_then_softmax` aggregation, thresholds, and order:
`human`, `animal`, `object`, `other`.

The image encoder outputs one `[1,768]` embedding. Text prototypes are derived
offline from the pinned source snapshot and are individually normalized. The
runtime compares each image vector to every prototype, applies the frozen scale
and bias, averages logits per category, then applies softmax.

`encoderVersion`, `subjectHintPolicyVersion`, and `masterRankerVersion` are
independent values in the manifest. Changing prompts or thresholds changes the
policy version; it must not masquerade as a binary change.

## Safety behavior

The loader rejects absent files, invalid JSON, package names, hashes, prompt
contract, preprocess, ONNX Runtime version, non-CPU provider, output shape, or
prototype shape. It reports a safe code only. The subject hint becomes neutral;
automatic ranking remains blocked. Neither path can schedule GPU work.

With `INCUBATOR_AUTO_RANKING_ENABLED=false`, rank results are emitted only as
sanitized aggregate observations. No Master is approved, no selection is
persisted, and poses are not scheduled. SigLIP may become a ranking gate only
after a separately approved evaluation against real Masters with known human
choices.

## Reproducibility and validation

`tools/export_siglip_onnx.py` accepts a pre-fetched local source directory and
uses `local_files_only=True`; it cannot download weights. It exports opset 17,
generates prototypes, and writes the manifest. `tools/verify_siglip_artifact.py`
compares normalized ONNX output with the pinned Transformers source using the
same preprocessing and fails outside tolerance. The CPU benchmark exists both
as a controlled Modal function and offline helper; capacity must be decided
from the Modal CPU measurement, not a workstation result.

The controlled exporter environment is pinned in
`tools/requirements-siglip-export.txt`. It is intentionally separate from the
Modal image: `transformers`, `torch`, and ONNX export tooling are not runtime
dependencies of an Incubator request.

## Consequences

The CPU image adds exact dependencies `numpy==2.1.3` and
`onnxruntime==1.20.1`. The artifact can be hundreds of MB and may increase cold
start and RSS. Provisioning requires a separate approval after benchmark,
checksum, legal provenance, and shadow-quality review.

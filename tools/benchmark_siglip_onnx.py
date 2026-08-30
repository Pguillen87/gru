"""Local preflight benchmark; Production capacity must use Modal CPU results."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modal_service.incubator import SiglipOnnxVisualEncoder


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[max(0, min(len(ordered) - 1, round((len(ordered) - 1) * fraction)))]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--iterations", type=int, default=20)
    arguments = parser.parse_args()
    if not 1 <= arguments.iterations <= 100:
        raise SystemExit("--iterations must be between 1 and 100")
    started = time.perf_counter()
    encoder = SiglipOnnxVisualEncoder(arguments.artifact_dir)
    load_ms = (time.perf_counter() - started) * 1000
    content, samples = arguments.image.read_bytes(), []
    for _ in range(arguments.iterations):
        started = time.perf_counter()
        encoder.classify(content)
        samples.append((time.perf_counter() - started) * 1000)
    try:
        import resource
        rss_kib: int | None = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    except ImportError:
        rss_kib = None
    print(json.dumps({"encoder": encoder.provenance(), "loadMs": round(load_ms, 2), "iterations": arguments.iterations, "p50Ms": round(percentile(samples, .5), 2), "p95Ms": round(percentile(samples, .95), 2), "rssKiB": rss_kib}, sort_keys=True))


if __name__ == "__main__":
    main()

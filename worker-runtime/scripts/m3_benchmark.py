"""KARMO Worker Runtime -- M3 acceleration benchmark (Phase 12).

Real, local, bounded measurements only: Python CPU work, hashing, and a
real pytest run against the synthetic fixture suite -- all through the
SAME sandboxed capability handlers a real job would use, not a separate
unsandboxed fast path. Optional MLX/Metal probes report status only (no
model install, no weight download). Does NOT compare against KARMO
production -- that comparison requires directly measuring both sides
together, which this workload explicitly does not do.

Usage: worker-runtime/venv/bin/python scripts/m3_benchmark.py
Writes docs/evidence/worker-runtime/BENCHMARK_RESULTS.json
"""

import json
import sys
import time
from pathlib import Path

_APP = Path(__file__).resolve().parent.parent / "app"
sys.path.insert(0, str(_APP))

import capabilities  # noqa: F401 -- registers handlers
import resource_discovery
from sandbox import run_capability

FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "allowed_workspace"
OUTPUT_PATH = Path(__file__).resolve().parent.parent.parent / "docs" / "evidence" / "worker-runtime" / "BENCHMARK_RESULTS.json"


def _timed_capability(capability_id, payload, *, timeout_seconds, allowed_root=None):
    start = time.monotonic()
    output, summary, duration, evidence = run_capability(
        capability_id, payload, timeout_seconds=timeout_seconds, allowed_root=allowed_root,
    )
    wall = time.monotonic() - start
    return {"capability_id": capability_id, "output": output, "duration_seconds": duration, "wall_seconds": wall}


def run_benchmark():
    results = {
        "machine": "KARMO-DEV01",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "hardware": resource_discovery.full_report(),
        "measurements": [],
        "notes": [
            "All measurements taken through the real sandboxed capability handlers, "
            "not an unsandboxed fast path -- these are the numbers a real worker job would see.",
            "No comparison against KARMO production is made here -- that requires directly "
            "measuring both sides together, out of scope for this workload.",
            "No model weights were downloaded or installed to produce these numbers.",
        ],
    }

    # CPU-bound hash-loop work, several sizes.
    for iterations in (100_000, 1_000_000, 5_000_000):
        results["measurements"].append(
            _timed_capability("resource_benchmark", {"iterations": iterations}, timeout_seconds=30)
        )

    # Real SHA-256 hashing of the fixture file.
    results["measurements"].append(
        _timed_capability("hash_verify", {"path": "sample_document.txt"}, timeout_seconds=30, allowed_root=FIXTURES)
    )

    # Real pytest subprocess execution (interpreter startup + collection + run).
    results["measurements"].append(
        _timed_capability("pytest", {"test_dir": "sample_tests"}, timeout_seconds=60, allowed_root=FIXTURES)
    )

    # Synthetic embedding-shaped vector work, several sizes.
    for vector_count in (100, 1_000, 10_000):
        results["measurements"].append(
            _timed_capability("embedding_benchmark_test", {"vector_count": vector_count}, timeout_seconds=30)
        )

    # Optional acceleration probes -- status only, never installs anything.
    results["measurements"].append(_timed_capability("media_probe_test", {}, timeout_seconds=15))
    results["measurements"].append(_timed_capability("local_model_probe", {}, timeout_seconds=15))

    return results


if __name__ == "__main__":
    report = run_benchmark()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(report, indent=2, default=str))
    print(f"wrote {OUTPUT_PATH}")
    print(json.dumps(report, indent=2, default=str))

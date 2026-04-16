import json
import sys
from pathlib import Path


def _get_metric(root: dict, name: str, key: str, default=0):
    try:
        return root["metrics"][name]["values"].get(key, default)
    except Exception:
        return default


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python scripts/summarize_benchmark.py <summary.json>")
        return 1
    path = Path(sys.argv[1])
    if not path.exists():
        print(f"File not found: {path}")
        return 1
    data = json.loads(path.read_text(encoding="utf-8"))
    p95_ms = float(_get_metric(data, "http_req_duration", "p(95)", 0))
    p99_ms = float(_get_metric(data, "http_req_duration", "p(99)", 0))
    fail_rate = float(_get_metric(data, "http_req_failed", "rate", 0))
    req_rate = float(_get_metric(data, "http_reqs", "rate", 0))
    print("=== Benchmark Summary ===")
    print(f"p95 latency (ms): {p95_ms:.2f}")
    print(f"p99 latency (ms): {p99_ms:.2f}")
    print(f"request rate (req/s): {req_rate:.2f}")
    print(f"error rate: {fail_rate:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

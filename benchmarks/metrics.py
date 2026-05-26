import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class Metric:
    name: str
    unit: str = "ms"
    samples: list[float] = field(default_factory=list)


class MetricsCollector:
    def __init__(self):
        self._metrics: dict[str, Metric] = {}
        self._metadata: dict = {}

    def set_metadata(self, **kwargs):
        self._metadata.update(kwargs)

    def record(self, name: str, value_ms: float):
        if name not in self._metrics:
            self._metrics[name] = Metric(name=name)
        self._metrics[name].samples.append(value_ms)

    def _compute(self, name: str) -> Optional[dict]:
        m = self._metrics.get(name)
        if not m or not m.samples:
            return None

        samples = sorted(m.samples)
        n = len(samples)
        total = sum(samples)
        mean = total / n

        if n % 2 == 1:
            median = samples[n // 2]
        else:
            median = (samples[n // 2 - 1] + samples[n // 2]) / 2

        p95_idx = max(0, min(n - 1, int(math.ceil(n * 0.95) - 1)))
        p99_idx = max(0, min(n - 1, int(math.ceil(n * 0.99) - 1)))

        variance = sum((x - mean) ** 2 for x in samples) / (n - 1) if n > 1 else 0
        stddev = math.sqrt(variance)

        return {
            "count": n,
            "min_ms": round(min(samples), 3),
            "max_ms": round(max(samples), 3),
            "avg_ms": round(mean, 3),
            "median_ms": round(median, 3),
            "p95_ms": round(samples[p95_idx], 3),
            "p99_ms": round(samples[p99_idx], 3),
            "stddev_ms": round(stddev, 3),
            "unit": m.unit,
        }

    def result(self, name: str) -> Optional[dict]:
        return self._compute(name)

    def table(self) -> str:
        names = sorted(self._metrics.keys())
        if not names:
            return "(no metrics collected)"

        rows = []
        header = (
            f"{'Metric':<50} {'Count':>6} {'Min(ms)':>10} {'Max(ms)':>10} "
            f"{'Avg(ms)':>10} {'Median(ms)':>10} {'P95(ms)':>10} {'P99(ms)':>10}"
        )
        sep = "-" * len(header)
        rows.append(header)
        rows.append(sep)

        for name in names:
            r = self._compute(name)
            if r is None:
                continue
            rows.append(
                f"{name:<50} {r['count']:>6} {r['min_ms']:>10.3f} {r['max_ms']:>10.3f} "
                f"{r['avg_ms']:>10.3f} {r['median_ms']:>10.3f} {r['p95_ms']:>10.3f} {r['p99_ms']:>10.3f}"
            )

        return "\n".join(rows)

    def to_json(self) -> str:
        out = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": self._metadata,
            "metrics": {},
        }
        for name in sorted(self._metrics.keys()):
            r = self._compute(name)
            if r:
                out["metrics"][name] = r
        return json.dumps(out, indent=2)

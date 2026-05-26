# Performance Benchmark Results

Generated: 2026-05-26

## How to Run

```bash
# Quick standalone (components + DB, 10 iterations)
python benchmarks/run.py --mode quick --standalone

# Full suite against live API
python benchmarks/run.py --mode full --json report.json

# Full suite with DeepSeek AI tests
python benchmarks/run.py --mode full --api-url http://localhost:8000/events --include-ai

# Single scenario
python benchmarks/run.py --scenario flows --iterations 50
```

## Results — Quick Mode (10 iterations)

### Component Benchmarks

| Metric | Min(ms) | Max(ms) | Avg(ms) | Median(ms) | P95(ms) |
|--------|---------|---------|---------|------------|---------|
| spaCy extract_entities (minimal) | 10.4 | 13.9 | 11.7 | 11.4 | 13.9 |
| spaCy extract_entities (typical) | 14.7 | 20.9 | 15.9 | 15.4 | 20.9 |
| spaCy extract_entities (complex) | 22.2 | 37.4 | 27.6 | 27.0 | 37.4 |
| normalize_and_clean | 0.006 | 0.028 | 0.015 | 0.014 | 0.028 |
| rank_title_candidates | 0.023 | 0.103 | 0.058 | 0.055 | 0.103 |
| extract_links | 0.002 | 0.227 | 0.012 | 0.003 | 0.227 |
| extract_fee | 0.033 | 1.533 | 0.096 | 0.042 | 1.533 |
| check_mycsd | 0.004 | 0.120 | 0.011 | 0.005 | 0.120 |
| extract_dates (minimal) | 129.4 | 3998.3 | 524.7 | 139.6 | 3998.3 |
| extract_dates (typical) | 242.1 | 329.8 | 269.2 | 263.0 | 329.8 |
| extract_dates (complex) | 374.7 | 444.6 | 413.3 | 413.8 | 444.6 |

### Database Benchmarks (scaling test)

| Metric | 0 docs | 10 docs | 100 docs | 1000 docs |
|--------|--------|---------|----------|-----------|
| get_events (all) | 4ms | 92ms | 458ms | **4547ms** |
| get_events (search) | — | 14ms | 99ms | **926ms** |
| get_events (status filter) | — | 183ms | 992ms | **9069ms** |
| get_event_by_id | — | 8ms | 8ms | 8ms |
| add_event | 7ms | 3ms | 3ms | 3ms |
| check_event_exists | 4ms | 4ms | 4ms | 4ms |

### API Endpoint Benchmarks

| Metric | Min(ms) | Max(ms) | Avg(ms) |
|--------|---------|---------|---------|
| GET /events (no filters) | 733.6 | 946.2 | 823.3 |
| GET /events (search) | 541.6 | 615.5 | 583.7 |
| GET /events (filters) | 658.2 | 817.5 | 739.1 |
| POST /events | 556.1 | 761.7 | 618.0 |
| POST /events/process (minimal) | 1513.2 | 3114.8 | 1966.9 |
| POST /events/process (typical) | 1492.2 | 1916.0 | 1722.6 |
| POST /events/process (complex) | 1527.1 | 1863.2 | 1678.4 |
| GET /events/404 | 545.8 | 764.6 | 600.1 |

### Button Flow Benchmarks

| Metric | Min(ms) | Max(ms) | Avg(ms) |
|--------|---------|---------|---------|
| flow browse.list | 1315.4 | 1541.3 | 1418.9 |
| flow browse.total | 1911.7 | 2240.2 | 2024.0 |
| flow search.total | 1204.7 | 1357.8 | 1266.7 |
| flow filter.total | 2917.1 | 3797.9 | 3188.5 |
| flow create.total | 583.3 | 731.3 | 636.0 |
| flow pagination.total | 4244.9 | 4782.9 | 4449.4 |
| flow process.total | 582.7 | 726.5 | 634.2 |
| flow batch.total (3 msgs) | 1707.4 | 1738.6 | 1721.3 |

## Critical Bottlenecks

1. **`get_events(status filter)` at 1000 docs → 9s.** Fetches ALL documents, calls `compute_status()` + `dateparser.parse()` on each. O(N) pagination. No MongoDB index.

2. **`api_client.py` creates new httpx client per call** — no connection reuse, adds overhead.

3. **dateparser outliers spike to 4s** — `compute_status()` calls it per document.

4. **POST /events/process** — 1.5-3.1s due to NLP + extraction pipeline. Adds ~1.5s to every forwarded message.

#!/usr/bin/env python3
"""
USM Event Hub — Performance Benchmark Runner

Measures latency for bot components (spaCy, regex, AI, formatting),
database operations, API endpoints, and simulated button click flows.

Usage:
    # Quick standalone (components + DB only, 10 iterations)
    python benchmarks/run.py --mode quick --standalone

    # Full suite against live API
    python benchmarks/run.py --mode full --api-url http://localhost:8000/events

    # Full suite with DeepSeek AI tests
    python benchmarks/run.py --mode full --api-url http://localhost:8000/events --include-ai

    # Specific scenario
    python benchmarks/run.py --scenario flows --iterations 50

    # JSON export
    python benchmarks/run.py --mode full --json report.json
"""

import argparse
import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from benchmarks.metrics import MetricsCollector
from benchmarks.config import DEFAULT_API_URL, QUICK_ITERATIONS, FULL_ITERATIONS, PERF_DATA_SIZES


def parse_args():
    parser = argparse.ArgumentParser(description="USM Event Hub Performance Benchmarks")
    parser.add_argument(
        "--mode", choices=["quick", "full"], default="quick",
        help="quick=10 iterations, full=100 iterations (default: quick)",
    )
    parser.add_argument(
        "--standalone", action="store_true",
        help="Skip API-dependent tests (components + DB only)",
    )
    parser.add_argument(
        "--api-url", default=DEFAULT_API_URL,
        help=f"API base URL (default: {DEFAULT_API_URL})",
    )
    parser.add_argument(
        "--scenario", choices=["components", "database", "api", "flows", "all"], default="all",
        help="Run only a specific scenario (default: all)",
    )
    parser.add_argument(
        "--include-ai", action="store_true",
        help="Include DeepSeek AI benchmarks (warns about API costs)",
    )
    parser.add_argument(
        "--iterations", type=int, default=None,
        help="Override iteration count for all scenarios",
    )
    parser.add_argument(
        "--json", type=str, default=None,
        help="Export results as JSON to FILE",
    )
    return parser.parse_args()


async def check_api_reachable(api_url: str) -> bool:
    import httpx
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            resp = await c.get(api_url)
            return resp.status_code < 500
    except Exception:
        return False


async def main():
    args = parse_args()

    if args.include_ai:
        print("\n  [WARN] --include-ai enabled. DeepSeek API calls incur costs.")
        print("         Limited to 5 iterations per test.\n")

    iterations = args.iterations or (QUICK_ITERATIONS if args.mode == "quick" else FULL_ITERATIONS)
    collector = MetricsCollector()
    collector.set_metadata(
        mode=args.mode,
        standalone=args.standalone,
        iterations=iterations,
        ai_tests=args.include_ai,
        api_url=args.api_url,
    )

    print(f"  Mode: {args.mode} ({iterations} iterations)")
    print(f"  Standalone: {args.standalone}")
    print(f"  Scenario: {args.scenario}")
    print(f"  AI tests: {args.include_ai}")
    print()

    run_all = args.scenario == "all"

    if run_all or args.scenario == "components":
        print("[1/4] Component benchmarks (spaCy, regex, formatting)...")
        from benchmarks.scenarios.test_components import run_component_benchmarks
        await run_component_benchmarks(collector, iterations, include_ai=args.include_ai)
        print("      Done.")

    if run_all or args.scenario == "database":
        print(f"[2/4] Database benchmarks (sizes: {PERF_DATA_SIZES})...")
        from benchmarks.scenarios.test_database import run_database_benchmarks
        await run_database_benchmarks(collector, iterations, data_sizes=PERF_DATA_SIZES)
        print("      Done.")

    if (run_all or args.scenario == "api") and not args.standalone:
        print(f"[3/4] API endpoint benchmarks against {args.api_url}...")
        api_ok = await check_api_reachable(args.api_url)
        if api_ok:
            from benchmarks.scenarios.test_api import run_api_benchmarks
            await run_api_benchmarks(collector, iterations, api_url=args.api_url)
            print("      Done.")
        else:
            print("      [SKIP] API not reachable.")

    if (run_all or args.scenario == "flows") and not args.standalone:
        print(f"[4/4] Button flow simulations against {args.api_url}...")
        api_ok = await check_api_reachable(args.api_url)
        if api_ok:
            from benchmarks.scenarios.test_flows import run_flow_benchmarks
            await run_flow_benchmarks(collector, iterations, api_url=args.api_url)
            print("      Done.")
        else:
            print("      [SKIP] API not reachable.")

    print("\n" + "=" * 80)
    print("PERFORMANCE BENCHMARK RESULTS")
    print("=" * 80)
    print(collector.table())

    if args.json:
        with open(args.json, "w") as f:
            f.write(collector.to_json())
        print(f"\nResults exported to: {args.json}")

    metric_count = len(collector._metrics)
    sample_count = sum(len(m.samples) for m in collector._metrics.values())
    print(f"\n  {metric_count} metrics, {sample_count} total samples collected.")


if __name__ == "__main__":
    asyncio.run(main())

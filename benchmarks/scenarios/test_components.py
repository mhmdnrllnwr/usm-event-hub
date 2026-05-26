import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from benchmarks.config import SAMPLE_SAMPLES, SAMPLE_EVENT_MINIMAL, SAMPLE_EVENT_FULL, AI_SAMPLE_ITERATIONS
from benchmarks.metrics import MetricsCollector


def _try_import(module_path, attr):
    try:
        import importlib
        mod = importlib.import_module(module_path)
        return getattr(mod, attr, None)
    except Exception:
        return None


async def run_component_benchmarks(collector: MetricsCollector, iterations: int, include_ai: bool = False):
    collector.set_metadata(ai_tests=include_ai)

    normalize_and_clean = _try_import("api.engine.nlp_handler", "normalize_and_clean")
    rank_title_candidates = _try_import("api.engine.nlp_handler", "rank_title_candidates")
    identify_title = _try_import("api.engine.nlp_handler", "identify_title_heuristically")
    extract_entities_fn = _try_import("api.engine.nlp_handler", "extract_entities")
    resolve_venue = _try_import("api.engine.nlp_handler", "resolve_venue")

    extract_links = _try_import("api.engine.regex_handler", "extract_links")
    extract_fee = _try_import("api.engine.regex_handler", "extract_fee")
    check_mycsd = _try_import("api.engine.regex_handler", "check_mycsd")
    extract_dates_and_times = _try_import("api.engine.regex_handler", "extract_dates_and_times")

    validate_title_fn = _try_import("api.engine.ai_handler", "validate_title")
    validate_event_fn = _try_import("api.engine.ai_handler", "validate_event")

    format_event = _try_import("bot.helpers", "format_event")
    format_event_compact = _try_import("bot.helpers", "format_event_compact")

    # --- SpaCy cold start ---
    cold_measured = False
    if extract_entities_fn:
        for label, text in SAMPLE_SAMPLES.items():
            if not cold_measured:
                t0 = time.perf_counter()
                extract_entities_fn(text)
                elapsed = (time.perf_counter() - t0) * 1000
                collector.record(f"spacy extract_entities ({label}) — cold start", elapsed)
                cold_measured = True
            for _ in range(iterations):
                t0 = time.perf_counter()
                extract_entities_fn(text)
                elapsed = (time.perf_counter() - t0) * 1000
                collector.record(f"spacy extract_entities ({label})", elapsed)

    if normalize_and_clean:
        for label, text in SAMPLE_SAMPLES.items():
            for _ in range(iterations):
                t0 = time.perf_counter()
                normalize_and_clean(text)
                elapsed = (time.perf_counter() - t0) * 1000
                collector.record(f"normalize_and_clean ({label})", elapsed)

    if rank_title_candidates:
        for label, text in SAMPLE_SAMPLES.items():
            for _ in range(iterations):
                t0 = time.perf_counter()
                rank_title_candidates(text)
                elapsed = (time.perf_counter() - t0) * 1000
                collector.record(f"rank_title_candidates ({label})", elapsed)

    if identify_title:
        for label, text in SAMPLE_SAMPLES.items():
            for _ in range(iterations):
                t0 = time.perf_counter()
                identify_title(text)
                elapsed = (time.perf_counter() - t0) * 1000
                collector.record(f"identify_title ({label})", elapsed)

    if extract_links:
        for label, text in SAMPLE_SAMPLES.items():
            for _ in range(iterations):
                t0 = time.perf_counter()
                extract_links(text)
                elapsed = (time.perf_counter() - t0) * 1000
                collector.record(f"extract_links ({label})", elapsed)

    if extract_fee:
        for label, text in SAMPLE_SAMPLES.items():
            for _ in range(iterations):
                t0 = time.perf_counter()
                extract_fee(text)
                elapsed = (time.perf_counter() - t0) * 1000
                collector.record(f"extract_fee ({label})", elapsed)

    if check_mycsd:
        for label, text in SAMPLE_SAMPLES.items():
            for _ in range(iterations):
                t0 = time.perf_counter()
                check_mycsd(text)
                elapsed = (time.perf_counter() - t0) * 1000
                collector.record(f"check_mycsd ({label})", elapsed)

    if extract_dates_and_times:
        for label, text in SAMPLE_SAMPLES.items():
            for _ in range(iterations):
                t0 = time.perf_counter()
                extract_dates_and_times(text)
                elapsed = (time.perf_counter() - t0) * 1000
                collector.record(f"extract_dates ({label})", elapsed)

    if format_event:
        for name, evt in [("minimal", SAMPLE_EVENT_MINIMAL), ("full", SAMPLE_EVENT_FULL)]:
            for _ in range(iterations):
                t0 = time.perf_counter()
                format_event(evt)
                elapsed = (time.perf_counter() - t0) * 1000
                collector.record(f"format_event ({name})", elapsed)

    if format_event_compact:
        for name, evt in [("minimal", SAMPLE_EVENT_MINIMAL), ("full", SAMPLE_EVENT_FULL)]:
            for _ in range(iterations):
                t0 = time.perf_counter()
                format_event_compact(evt)
                elapsed = (time.perf_counter() - t0) * 1000
                collector.record(f"format_event_compact ({name})", elapsed)

    if include_ai:
        if validate_title_fn and extract_entities_fn:
            for label, text in SAMPLE_SAMPLES.items():
                candidates = extract_entities_fn(text)["title_candidates"]
                for _ in range(AI_SAMPLE_ITERATIONS):
                    t0 = time.perf_counter()
                    await validate_title_fn(candidates, text)
                    elapsed = (time.perf_counter() - t0) * 1000
                    collector.record(f"validate_title ({label})", elapsed)

        if validate_event_fn and extract_entities_fn:
            for label, text in SAMPLE_SAMPLES.items():
                extracted = extract_entities_fn(text)
                candidates = extracted.get("title_candidates", [text.split("\n")[0]])
                for _ in range(AI_SAMPLE_ITERATIONS):
                    t0 = time.perf_counter()
                    await validate_event_fn(candidates, text, {"date_raw": None, "time_raw": None})
                    elapsed = (time.perf_counter() - t0) * 1000
                    collector.record(f"validate_event ({label})", elapsed)

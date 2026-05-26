import sys
import os
import time
import uuid

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from benchmarks.config import MONGO_DETAILS, PERF_DB_NAME, PERF_COLLECTION_PREFIX, PERF_DATA_SIZES, SAMPLE_EVENT_CREATE
from benchmarks.metrics import MetricsCollector


async def run_database_benchmarks(collector: MetricsCollector, iterations: int, data_sizes: list[int] = None):
    if data_sizes is None:
        data_sizes = PERF_DATA_SIZES

    # api/database.py does `from models import EventCreate` (no package prefix)
    api_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "api"))
    if api_dir not in sys.path:
        sys.path.insert(0, api_dir)

    try:
        from motor.motor_asyncio import AsyncIOMotorClient
        from api.database import get_events, get_event_by_id, check_event_exists, add_event, update_event, delete_event, compute_status
    except Exception as e:
        print(f"  [SKIP] DB benchmarks — import failed: {e}")
        return

    try:
        client = AsyncIOMotorClient(MONGO_DETAILS, serverSelectionTimeoutMS=2000)
        await client.admin.command("ping")
    except Exception:
        print("  [SKIP] DB benchmarks — MongoDB unreachable")
        return

    db = client[PERF_DB_NAME]
    coll_name = PERF_COLLECTION_PREFIX + uuid.uuid4().hex[:8]
    temp_collection = db[coll_name]

    import api.database as db_mod
    original_collection = db_mod.event_collection
    db_mod.event_collection = temp_collection

    try:
        for size in data_sizes:
            label_suffix = f"({size} docs)"

            if size > 0:
                docs = []
                for i in range(size):
                    doc = dict(SAMPLE_EVENT_CREATE)
                    doc["title"] = f"Benchmark Event {i} — {'Test' if i % 5 == 0 else 'Regular'}"
                    doc["start_date"] = "15 August 2026"
                    doc["raw_text"] = f"Event {i} description"
                    docs.append(doc)
                await temp_collection.insert_many(docs)

            for _ in range(iterations):
                t0 = time.perf_counter()
                await get_events(page=1, per_page=10)
                elapsed = (time.perf_counter() - t0) * 1000
                collector.record(f"get_events (all) {label_suffix}", elapsed)

            if size > 0:
                for _ in range(iterations):
                    t0 = time.perf_counter()
                    await get_events(search_term="Test", page=1, per_page=10)
                    elapsed = (time.perf_counter() - t0) * 1000
                    collector.record(f"get_events (search) {label_suffix}", elapsed)

            if size > 0:
                for _ in range(iterations):
                    t0 = time.perf_counter()
                    await get_events(status="active", page=1, per_page=10)
                    elapsed = (time.perf_counter() - t0) * 1000
                    collector.record(f"get_events (status filter) {label_suffix}", elapsed)

            if size > 0:
                first = await temp_collection.find_one()
                if first:
                    eid = str(first["_id"])
                    for _ in range(iterations):
                        t0 = time.perf_counter()
                        await get_event_by_id(eid)
                        elapsed = (time.perf_counter() - t0) * 1000
                        collector.record(f"get_event_by_id {label_suffix}", elapsed)

            for _ in range(iterations):
                t0 = time.perf_counter()
                await check_event_exists("Benchmark Event 0", "15 August 2026")
                elapsed = (time.perf_counter() - t0) * 1000
                collector.record(f"check_event_exists {label_suffix}", elapsed)

            for _ in range(iterations):
                from api.models import EventCreate
                payload = EventCreate(**{**SAMPLE_EVENT_CREATE, "title": f"New Event {uuid.uuid4().hex[:6]}"})
                t0 = time.perf_counter()
                await add_event(payload)
                elapsed = (time.perf_counter() - t0) * 1000
                collector.record(f"add_event {label_suffix}", elapsed)

            if size > 0:
                await temp_collection.drop()

        sample_events = [
            {"end_date": "15 August 2026"},
            {"end_date": "15 May 2020"},
            {},
            {"end_date": "TBD"},
            {"end_date": None, "start_date": "15 August 2026"},
        ]
        for _ in range(iterations * 5):
            for evt in sample_events:
                t0 = time.perf_counter()
                compute_status(evt)
                elapsed = (time.perf_counter() - t0) * 1000
                collector.record(f"compute_status (single)", elapsed)

    finally:
        db_mod.event_collection = original_collection
        try:
            await temp_collection.drop()
        except Exception:
            pass
        client.close()

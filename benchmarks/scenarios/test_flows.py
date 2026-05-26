import time
import httpx

from benchmarks.config import DEFAULT_API_URL, HTTP_TIMEOUT, SAMPLE_SAMPLES, SAMPLE_EVENT_CREATE
from benchmarks.metrics import MetricsCollector


async def run_flow_benchmarks(collector: MetricsCollector, iterations: int, api_url: str = None):
    if api_url is None:
        api_url = DEFAULT_API_URL

    conn_kwargs = {"timeout": httpx.Timeout(HTTP_TIMEOUT)}

    try:
        async with httpx.AsyncClient(**conn_kwargs) as client:
            resp = await client.get(api_url)
            resp.raise_for_status()
    except Exception as e:
        print(f"  [SKIP] Button flow benchmarks — API unreachable: {e}")
        return

    async def one_shot_get(path="", params=None):
        async with httpx.AsyncClient(**conn_kwargs) as c:
            return await c.get(f"{api_url}{path}", params=params)

    async def one_shot_post(path="", json=None):
        async with httpx.AsyncClient(**conn_kwargs) as c:
            return await c.post(f"{api_url}{path}", json=json)

    async def one_shot_put(path="", json=None):
        async with httpx.AsyncClient(**conn_kwargs) as c:
            return await c.put(f"{api_url}{path}", json=json)

    async def one_shot_delete(path=""):
        async with httpx.AsyncClient(**conn_kwargs) as c:
            return await c.delete(f"{api_url}{path}")

    process_url = api_url.rstrip("/events").rstrip("/") + "/events/process"

    # Pre-seed: create events for listing flows
    seeded_ids = []
    for i in range(15):
        payload = dict(SAMPLE_EVENT_CREATE)
        payload["title"] = f"Flow Test Event {i}"
        payload["raw_text"] = f"Flow Test Event {i}\n15 Aug 2026\nFree"
        resp = await one_shot_post(json=payload)
        if resp.status_code == 200:
            data = resp.json()
            eid = data.get("event", {}).get("_id") or data.get("_id")
            if eid:
                seeded_ids.append(eid)

    try:
        # Flow 1: Browse Active Events
        for _ in range(iterations):
            flow_t0 = time.perf_counter()
            st0 = time.perf_counter()
            resp = await one_shot_get(params={"status": "active", "page": 1, "per_page": 5, "sort": "date_asc"})
            collector.record("flow browse.list", (time.perf_counter() - st0) * 1000)
            if resp.status_code == 200:
                events = resp.json().get("events", [])
                if events:
                    eid = events[0]["_id"]
                    st1 = time.perf_counter()
                    await one_shot_get(f"/{eid}")
                    collector.record("flow browse.view", (time.perf_counter() - st1) * 1000)
            collector.record("flow browse.total", (time.perf_counter() - flow_t0) * 1000)

        # Flow 2: Search + View
        for _ in range(iterations):
            flow_t0 = time.perf_counter()
            st0 = time.perf_counter()
            resp = await one_shot_get(params={"search": "Flow Test", "page": 1, "per_page": 5})
            collector.record("flow search.query", (time.perf_counter() - st0) * 1000)
            if resp.status_code == 200:
                events = resp.json().get("events", [])
                if events:
                    eid = events[0]["_id"]
                    st1 = time.perf_counter()
                    await one_shot_get(f"/{eid}")
                    collector.record("flow search.view", (time.perf_counter() - st1) * 1000)
            collector.record("flow search.total", (time.perf_counter() - flow_t0) * 1000)

        # Flow 3: Filter Browse
        for _ in range(iterations):
            flow_t0 = time.perf_counter()
            st0 = time.perf_counter()
            await one_shot_get(params={"status": "upcoming", "per_page": 5})
            collector.record("flow filter.status", (time.perf_counter() - st0) * 1000)
            st1 = time.perf_counter()
            await one_shot_get(params={"status": "upcoming", "fee": "free", "per_page": 5})
            collector.record("flow filter.fee", (time.perf_counter() - st1) * 1000)
            st2 = time.perf_counter()
            await one_shot_get(params={"status": "upcoming", "fee": "free", "has_mycsd": "true", "per_page": 5})
            collector.record("flow filter.mycsd", (time.perf_counter() - st2) * 1000)
            collector.record("flow filter.total", (time.perf_counter() - flow_t0) * 1000)

        # Flow 4: Create Event
        for _ in range(iterations):
            flow_t0 = time.perf_counter()
            st0 = time.perf_counter()
            resp = await one_shot_post(json={
                "title": "Flow Created Event",
                "start_date": "15 August 2026",
                "end_date": "16 August 2026",
                "start_time": "9:00 AM",
                "end_time": "5:00 PM",
                "venue": "DK1",
                "fee": "Free",
                "registration_link": "https://example.com",
                "has_mycsd": True,
                "raw_text": "",
            })
            collector.record("flow create.post", (time.perf_counter() - st0) * 1000)
            if resp.status_code == 200:
                data = resp.json()
                eid = data.get("event", {}).get("_id") or data.get("_id")
                if eid:
                    st1 = time.perf_counter()
                    await one_shot_get(f"/{eid}")
                    collector.record("flow create.verify", (time.perf_counter() - st1) * 1000)
            collector.record("flow create.total", (time.perf_counter() - flow_t0) * 1000)

        # Flow 5: Process Forwarded Message
        for _ in range(max(1, iterations // 2)):
            flow_t0 = time.perf_counter()
            st0 = time.perf_counter()
            resp = await one_shot_post(path="", json={"text": SAMPLE_SAMPLES["typical"], "creator_id": 999})
            collector.record("flow process.extract", (time.perf_counter() - st0) * 1000)
            if resp.status_code == 200:
                data = resp.json()
                eid = data.get("event", {}).get("_id") or data.get("_id")
                if eid:
                    st1 = time.perf_counter()
                    await one_shot_get(f"/{eid}")
                    collector.record("flow process.view", (time.perf_counter() - st1) * 1000)
            collector.record("flow process.total", (time.perf_counter() - flow_t0) * 1000)

        # Flow 6: Lifecycle
        for _ in range(max(1, iterations // 2)):
            flow_t0 = time.perf_counter()
            st0 = time.perf_counter()
            resp = await one_shot_post(json={
                "title": "Lifecycle Event",
                "start_date": "15 August 2026",
                "fee": "Free",
                "raw_text": "Lifecycle Event\n15 Aug 2026",
            })
            collector.record("flow lifecycle.create", (time.perf_counter() - st0) * 1000)
            eid = None
            if resp.status_code == 200:
                data = resp.json()
                eid = data.get("event", {}).get("_id") or data.get("_id")
            if eid:
                st1 = time.perf_counter()
                await one_shot_get(f"/{eid}")
                collector.record("flow lifecycle.view", (time.perf_counter() - st1) * 1000)
                st2 = time.perf_counter()
                await one_shot_put(f"/{eid}", json={"title": "Lifecycle Event Updated"})
                collector.record("flow lifecycle.edit", (time.perf_counter() - st2) * 1000)
                st3 = time.perf_counter()
                await one_shot_delete(f"/{eid}")
                collector.record("flow lifecycle.delete", (time.perf_counter() - st3) * 1000)
            collector.record("flow lifecycle.total", (time.perf_counter() - flow_t0) * 1000)

        # Flow 7: Pagination Walk
        for _ in range(iterations):
            flow_t0 = time.perf_counter()
            params = {"status": "all", "per_page": 5, "sort": "date_asc"}
            for page in [1, 2, 3]:
                st = time.perf_counter()
                params["page"] = str(page)
                await one_shot_get(params=dict(params))
                collector.record(f"flow pagination.page{page}", (time.perf_counter() - st) * 1000)
            collector.record("flow pagination.total", (time.perf_counter() - flow_t0) * 1000)

        # Flow 8: Batch Mode
        for batch in range(max(1, iterations // 3)):
            flow_t0 = time.perf_counter()
            for label in ["minimal", "typical", "complex"]:
                st = time.perf_counter()
                await one_shot_post(
                    path="",
                    json={"text": SAMPLE_SAMPLES[label], "creator_id": 999, "skip_ai": True},
                )
                collector.record(f"flow batch.process_{label}", (time.perf_counter() - st) * 1000)
            collector.record("flow batch.total", (time.perf_counter() - flow_t0) * 1000)

        # Flow 9: My Events
        for _ in range(iterations):
            st = time.perf_counter()
            await one_shot_get(params={"creator_id": 999, "page": 1, "per_page": 5})
            collector.record("flow myevents.list", (time.perf_counter() - st) * 1000)

    finally:
        for eid in seeded_ids:
            try:
                await one_shot_delete(f"/{eid}")
            except Exception:
                pass

import time
import httpx

from benchmarks.config import DEFAULT_API_URL, HTTP_TIMEOUT, SAMPLE_SAMPLES
from benchmarks.metrics import MetricsCollector


async def run_api_benchmarks(collector: MetricsCollector, iterations: int, api_url: str = None):
    if api_url is None:
        api_url = DEFAULT_API_URL

    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            resp = await client.get(api_url)
            resp.raise_for_status()
    except Exception as e:
        print(f"  [SKIP] API endpoint benchmarks — unreachable: {e}")
        return

    conn_kwargs = {"timeout": httpx.Timeout(HTTP_TIMEOUT)}

    async def bench(name: str, fn, n: int = iterations):
        for _ in range(n):
            t0 = time.perf_counter()
            await fn()
            elapsed = (time.perf_counter() - t0) * 1000
            collector.record(name, elapsed)

    async def get_events_empty():
        async with httpx.AsyncClient(**conn_kwargs) as c:
            await c.get(api_url)
    await bench("GET /events (no filters)", get_events_empty)

    async def get_events_search():
        async with httpx.AsyncClient(**conn_kwargs) as c:
            await c.get(api_url, params={"search": "HACKATHON"})
    await bench("GET /events (search)", get_events_search)

    async def get_events_filtered():
        async with httpx.AsyncClient(**conn_kwargs) as c:
            await c.get(api_url, params={"status": "active", "fee": "free", "page": 1, "per_page": 5})
    await bench("GET /events (filters)", get_events_filtered)

    event_id = None
    async def post_event():
        nonlocal event_id
        payload = {
            "title": "API Bench Event",
            "start_date": "15 August 2026",
            "fee": "Free",
            "raw_text": "API Bench Event",
        }
        async with httpx.AsyncClient(**conn_kwargs) as c:
            resp = await c.post(api_url, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                event_id = data.get("event", {}).get("_id") or data.get("_id")
    await bench("POST /events", post_event)

    if event_id:
        async def get_event():
            async with httpx.AsyncClient(**conn_kwargs) as c:
                await c.get(f"{api_url}/{event_id}")
        await bench("GET /events/{id}", get_event)

        async def put_event():
            async with httpx.AsyncClient(**conn_kwargs) as c:
                await c.put(f"{api_url}/{event_id}", json={"title": "Updated Bench Event"})
        await bench("PUT /events/{id}", put_event)

        async def delete_event():
            async with httpx.AsyncClient(**conn_kwargs) as c:
                await c.delete(f"{api_url}/{event_id}")
        await bench("DELETE /events/{id}", delete_event)

    process_url = api_url.rstrip("/events").rstrip("/") + "/events/process"
    for label, text in SAMPLE_SAMPLES.items():
        t = text
        async def post_process():
            async with httpx.AsyncClient(**conn_kwargs) as c:
                await c.post(process_url, json={"text": t, "creator_id": 0})
        await bench(f"POST /events/process ({label})", post_process, n=max(1, iterations // 2))

    async def get_404():
        async with httpx.AsyncClient(**conn_kwargs) as c:
            await c.get(f"{api_url}/000000000000000000000000")
    await bench("GET /events/404", get_404)

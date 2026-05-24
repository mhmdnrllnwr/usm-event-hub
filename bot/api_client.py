import httpx
from config import API_URL, PROCESS_URL

TIMEOUT = 30.0


async def fetch_events(params: dict | None = None) -> dict | None:
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            resp = await client.get(API_URL, params=params or {})
            return resp.json()
        except Exception:
            return None


async def fetch_event(event_id: str) -> dict | None:
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            resp = await client.get(f"{API_URL}/{event_id}")
            data = resp.json()
            return data.get("event")
        except Exception:
            return None


async def create_event(payload: dict) -> tuple[dict | None, str | None]:
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            resp = await client.post(API_URL, json=payload)
            if resp.status_code == 200:
                return resp.json(), None
            else:
                detail = resp.json().get("detail", "Unknown error")
                return None, str(detail)
        except Exception as e:
            return None, str(e)


async def update_event(event_id: str, updates: dict) -> tuple[bool, str]:
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            resp = await client.put(f"{API_URL}/{event_id}", json=updates)
            if resp.status_code == 200:
                return True, ""
            else:
                return False, resp.text
        except Exception as e:
            return False, str(e)


async def delete_event(event_id: str) -> bool:
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            resp = await client.delete(f"{API_URL}/{event_id}")
            return resp.status_code == 200
        except Exception:
            return False


async def process_forwarded(payload: dict, skip_ai: bool = False) -> dict | None:
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            if skip_ai:
                payload = {**payload, "skip_ai": True}
            resp = await client.post(PROCESS_URL, json=payload)
            if resp.status_code == 200:
                return resp.json()
            return {"status_code": resp.status_code}
        except Exception:
            return None


async def fetch_image(image_url: str) -> bytes | None:
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            resp = await client.get(image_url)
            return resp.content
        except Exception:
            return None

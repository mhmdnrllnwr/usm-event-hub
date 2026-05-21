import json
import os
import re
import logging
import httpx
from .config import DEEPSEEK_API_KEY_ENV, DEEPSEEK_API_URL, DEEPSEEK_MODEL, DEEPSEEK_TIMEOUT_SECONDS

logger = logging.getLogger(__name__)

def _build_prompt(candidates: list[str], raw_text: str) -> str:
    """Build prompt for DeepSeek title validation."""
    candidate_lines = "\n".join(
        f"{i+1}. {line}" for i, line in enumerate(candidates)
    )
    return (
        f"Given this event announcement message:\n\n"
        f"<raw_text>\n{raw_text}\n</raw_text>\n\n"
        f"Current title candidates from scoring:\n{candidate_lines}\n\n"
        f"Which line is the correct event title? Choose from candidates above, "
        f"or if none match, extract the correct title from the message directly.\n\n"
        f"Respond in JSON format only:\n{{\"title\": \"correct event title\"}}"
    )

def _parse_response(response_text: str) -> str | None:
    """Extract title from DeepSeek JSON response. Returns None if parsing fails."""
    try:
        data = json.loads(response_text)
        title = data.get("title")
        return title.strip() if title else None
    except (json.JSONDecodeError, AttributeError):
        match = re.search(r'\{[^}]*"title"[^}]*\}', response_text, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group())
                title = data.get("title")
                return title.strip() if title else None
            except json.JSONDecodeError:
                pass
        return None

async def validate_title(
    candidates: list[str],
    raw_text: str,
    api_key: str | None = None
) -> str | None:
    """
    Call DeepSeek-chat to validate title from candidates.
    Returns validated/corrected title (may differ from all candidates)
    or None on failure (caller falls back to heuristic).
    """
    if not candidates:
        return None

    key = api_key or os.getenv(DEEPSEEK_API_KEY_ENV)
    if not key:
        logger.warning("DEEPSEEK_API_KEY not set, skipping AI validation")
        return None

    prompt = _build_prompt(candidates, raw_text)

    try:
        async with httpx.AsyncClient(timeout=DEEPSEEK_TIMEOUT_SECONDS) as client:
            resp = await client.post(
                DEEPSEEK_API_URL,
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": DEEPSEEK_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "max_tokens": 100,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            return _parse_response(content)
    except httpx.TimeoutException:
        logger.error("DeepSeek API timeout")
    except httpx.HTTPStatusError as e:
        logger.error(f"DeepSeek API error: {e.response.status_code} {e.response.text}")
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        logger.error(f"DeepSeek response parse error: {e}")

    return None


def _build_event_prompt(
    title_candidates: list[str],
    raw_text: str,
    extracted: dict
) -> str:
    """Build prompt for DeepSeek to verify title, date, and time."""
    candidate_lines = "\n".join(
        f"{i+1}. {line}" for i, line in enumerate(title_candidates)
    )
    return (
        f"Given this event announcement message:\n\n"
        f"<raw_text>\n{raw_text}\n</raw_text>\n\n"
        f"**Title Verification**\n"
        f"Current title candidates from scoring:\n{candidate_lines}\n\n"
        f"Which line is the correct event title? Choose from candidates above, "
        f"or if none match, extract the correct title from the message directly.\n\n"
        f"**Date Verification**\n"
        f"Extracted date: \"{extracted.get('date_raw', 'None')}\"\n"
        f"Is this the correct event date? If wrong, extract the correct event date "
        f"(not registration deadline). Leave empty string if no date found.\n\n"
        f"**Time Verification**\n"
        f"Extracted time: \"{extracted.get('time_raw', 'None')}\"\n"
        f"Is this the correct event time? If wrong, extract the correct time. "
        f"Leave empty string if no time found.\n\n"
        f"Respond in JSON format only:\n"
        f"{{\"title\": \"correct title\", \"date\": \"correct date or empty\", \"time\": \"correct time or empty\"}}"
    )


def _parse_event_response(response_text: str) -> dict | None:
    """Extract {title, date, time} from DeepSeek JSON. Returns None if parsing fails."""
    try:
        data = json.loads(response_text)
        return {
            "title": (data.get("title") or "").strip() or None,
            "date": (data.get("date") or "").strip() or None,
            "time": (data.get("time") or "").strip() or None,
        }
    except (json.JSONDecodeError, AttributeError):
        match = re.search(r'\{[^}]*"title"[^}]*"date"[^}]*"time"[^}]*\}', response_text, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group())
                return {
                    "title": (data.get("title") or "").strip() or None,
                    "date": (data.get("date") or "").strip() or None,
                    "time": (data.get("time") or "").strip() or None,
                }
            except json.JSONDecodeError:
                pass
        return None


async def validate_event(
    title_candidates: list[str],
    raw_text: str,
    extracted: dict,
    api_key: str | None = None
) -> dict | None:
    """
    Call DeepSeek to verify title, date, time.
    Returns dict with keys: title, date, time (each str or None).
    Returns None on failure (caller keeps heuristic values).
    """
    key = api_key or os.getenv(DEEPSEEK_API_KEY_ENV)
    if not key:
        logger.warning("DEEPSEEK_API_KEY not set, skipping AI validation")
        return None

    prompt = _build_event_prompt(title_candidates, raw_text, extracted)

    try:
        async with httpx.AsyncClient(timeout=DEEPSEEK_TIMEOUT_SECONDS) as client:
            resp = await client.post(
                DEEPSEEK_API_URL,
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": DEEPSEEK_MODEL,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.1,
                    "max_tokens": 150,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            return _parse_event_response(content)
    except httpx.TimeoutException:
        logger.error("DeepSeek API timeout")
    except httpx.HTTPStatusError as e:
        logger.error(f"DeepSeek API error: {e.response.status_code} {e.response.text}")
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        logger.error(f"DeepSeek response parse error: {e}")

    return None

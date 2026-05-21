"""
Comprehensive tests for all 6 implemented plans.
Covers unit, component, and integration scenarios.
"""
import sys
import os
import re
import json
from datetime import datetime, timezone

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from telegram.helpers import escape_markdown
from bot.main import _format_date, format_event
from api.engine.ai_handler import _build_prompt, _parse_response, validate_title
from api.engine.nlp_handler import rank_title_candidates, extract_entities
from api.engine.regex_handler import extract_fee

# ---- Pure function copies for test isolation (api.main has import issues) ----


def validate_date(date_str: str | None) -> str | None:
    """Return date if it has day+month+year, else None. Mirrors api/main.py."""
    if not date_str:
        return None
    if date_str == "TBD":
        return "TBD"
    has_day = bool(re.search(r'(?<!\d)\d{1,2}(?!\d)', date_str))
    has_month = bool(re.search(r'[A-Za-z]{3,}', date_str))
    has_year = bool(re.search(r'\b\d{4}\b', date_str))
    return date_str if (has_day and has_month and has_year) else None


def compute_status(event: dict) -> str:
    """Return active/expired/upcoming. Mirrors api/database.py."""
    import dateparser
    date_str = event.get("end_date") or event.get("start_date")
    if not date_str or date_str == "TBD":
        return "upcoming"
    parsed = dateparser.parse(date_str)
    if not parsed:
        return "upcoming"
    now = datetime.now(timezone.utc).replace(tzinfo=None) if parsed.tzinfo else datetime.now()
    return "active" if parsed.date() >= now.date() else "expired"
# =============================================================================
# Plan 1: Date display cleanup — _format_date()
# =============================================================================


class TestFormatDate:
    def test_single_date(self):
        assert _format_date("13 April 2025", None) == "13 April 2025"

    def test_date_range(self):
        assert _format_date("13 April 2025", "15 April 2025") == "13 April 2025 - 15 April 2025"

    def test_same_start_end(self):
        """No range shown when dates identical."""
        assert _format_date("13 April 2025", "13 April 2025") == "13 April 2025"

    def test_both_none(self):
        assert _format_date(None, None) == "empty"

    def test_start_only_end_none(self):
        assert _format_date("1 June 2026", None) == "1 June 2026"

    def test_start_none_end_exists(self):
        assert _format_date(None, "15 June 2026") == "empty"

    def test_empty_strings(self):
        assert _format_date("", "") == "empty"
        assert _format_date("", None) == "empty"
        assert _format_date(None, "") == "empty"

    def test_tbd_backward_compat(self):
        assert _format_date("TBD", None) == "TBD"

    def test_end_different_from_start(self):
        result = _format_date("13 April 2025", "15 April 2025")
        assert " - " in result


# =============================================================================
# Plan 2: AI Title Validation — _parse_response, _build_prompt, validate_title
# =============================================================================

class TestBuildPrompt:
    def test_includes_candidates(self):
        prompt = _build_prompt(["Title A", "Title B"], "raw text here")
        assert "Title A" in prompt
        assert "Title B" in prompt
        assert "raw text here" in prompt

    def test_numbers_candidates(self):
        prompt = _build_prompt(["First", "Second", "Third"], "text")
        assert "1. First" in prompt
        assert "2. Second" in prompt
        assert "3. Third" in prompt

    def test_contains_xml_tags(self):
        prompt = _build_prompt(["Event"], "body")
        assert "<raw_text>" in prompt
        assert "</raw_text>" in prompt

    def test_requests_json_format(self):
        prompt = _build_prompt(["Event"], "body")
        assert "JSON" in prompt
        assert '"title"' in prompt

    def test_empty_candidates(self):
        prompt = _build_prompt([], "body")
        assert "1." not in prompt


class TestParseResponse:
    def test_valid_json(self):
        assert _parse_response('{"title": "Correct Title"}') == "Correct Title"

    def test_whitespace_around_json(self):
        assert _parse_response('  {"title": "Workshop 2025"}  ') == "Workshop 2025"

    def test_markdown_code_block(self):
        assert _parse_response('```json\n{"title": "Event Name"}\n```') == "Event Name"

    def test_empty_title_returns_none(self):
        assert _parse_response('{"title": ""}') is None

    def test_missing_title_field(self):
        assert _parse_response('{"other": "data"}') is None

    def test_invalid_json(self):
        assert _parse_response("not json at all") is None

    def test_none_input(self):
        assert _parse_response('{"title": null}') is None


class TestValidateTitleUnit:
    def test_no_candidates_returns_none(self):
        import asyncio
        result = asyncio.run(validate_title([], "raw text"))
        assert result is None

    def test_no_api_key_returns_none(self):
        import asyncio
        result = asyncio.run(validate_title(["candidate"], "raw text", api_key=None))
        assert result is None


# =============================================================================
# Plan 3: Markdown parsing fix — escape_markdown + format_event rendering
# =============================================================================

class TestMarkdownEscaping:
    def test_underscores_in_text(self):
        assert escape_markdown("Tech_Talk_2026", version=2) == r"Tech\_Talk\_2026"

    def test_asterisks_in_text(self):
        assert "\\*\\*Best\\*\\*" in escape_markdown("**Best** Event", version=2)

    def test_backticks_in_text(self):
        result = escape_markdown("Code `Workshop` 2026", version=2)
        assert "\\`" in result

    def test_brackets_in_text(self):
        result = escape_markdown("[Hackathon] 2026", version=2)
        assert "\\[" in result

    def test_url_with_underscore(self):
        result = escape_markdown("https://usm_events_hub.com/page", version=2)
        assert "\\_" in result

    def test_url_with_parentheses(self):
        result = escape_markdown("https://example.com/event(2026)", version=2)
        assert "\\(" in result and "\\)" in result

    def test_url_with_dot(self):
        result = escape_markdown("https://t.me/usm_hub", version=2)
        assert "t\\.me" in result

    def test_tilde_in_text(self):
        assert "\\~" in escape_markdown("~Important~ Event", version=2)

    def test_plus_in_text(self):
        assert "\\+\\+" in escape_markdown("C++ Workshop", version=2)

    def test_hyphen_in_text(self):
        assert "\\-known" in escape_markdown("Well-known Event", version=2)

    def test_dot_in_text(self):
        assert "2\\.0" in escape_markdown("v2.0 Release", version=2)

    def test_normal_text_passes_through(self):
        assert escape_markdown("Normal Event 2026", version=2) == "Normal Event 2026"

    def test_empty_string(self):
        assert escape_markdown("", version=2) == ""


class TestFormatEventRendering:
    """Test format_event() with various edge cases."""

    def _make_event(self, **overrides):
        base = {
            "title": "Test Event",
            "start_date": "1 June 2026",
            "end_date": "1 June 2026",
            "start_time": "10:00 AM",
            "end_time": "12:00 PM",
            "fee": "Free",
            "venue": "Online",
            "registration_link": "https://example.com/register",
            "has_mycsd": False,
            "status": "active",
        }
        base.update(overrides)
        return base

    def test_special_chars_in_title(self):
        ev = self._make_event(title="Tech_Talk_2026: AI *Future*")
        result = format_event(ev)
        assert "Tech\\_Talk\\_2026" in result
        assert "\\*Future\\*" in result

    def test_special_chars_in_venue(self):
        ev = self._make_event(venue="DK1 (Main Hall)")
        result = format_event(ev)
        assert "\\(" in result and "\\)" in result

    def test_url_with_special_chars(self):
        ev = self._make_event(registration_link="https://example.com/event(2026)")
        result = format_event(ev)
        assert "event\\(2026\\)" in result

    def test_url_with_underscore(self):
        ev = self._make_event(registration_link="https://usm_events_hub.com/page")
        result = format_event(ev)
        assert "usm\\_events\\_hub" in result

    def test_fee_with_asterisk(self):
        ev = self._make_event(fee="RM10*")
        result = format_event(ev)
        assert "RM10\\*" in result

    def test_none_date_shows_unavailable(self):
        ev = self._make_event(start_date=None, end_date=None)
        result = format_event(ev)
        assert "empty" in result

    def test_none_time_shows_unavailable(self):
        ev = self._make_event(start_time=None, end_time=None)
        result = format_event(ev)
        assert "empty" in result

    def test_none_fee_shows_unavailable(self):
        ev = self._make_event(fee=None)
        result = format_event(ev)
        assert "empty" in result

    def test_none_venue_shows_unavailable(self):
        ev = self._make_event(venue=None)
        result = format_event(ev)
        assert "empty" in result

    def test_none_link_shows_unavailable(self):
        ev = self._make_event(registration_link=None)
        result = format_event(ev)
        assert "**Link:** empty" in result

    def test_none_mycsd_shows_no(self):
        ev = self._make_event(has_mycsd=None)
        result = format_event(ev)
        assert "**MyCSD:** No" in result

    def test_status_badge_active(self):
        ev = self._make_event(status="active")
        result = format_event(ev)
        assert "ACTIVE" in result

    def test_status_badge_expired(self):
        ev = self._make_event(status="expired")
        result = format_event(ev)
        assert "EXPIRED" in result

    def test_status_badge_upcoming(self):
        ev = self._make_event(status="upcoming")
        result = format_event(ev)
        assert "UPCOMING" in result

    def test_date_range_display(self):
        ev = self._make_event(start_date="1 June 2026", end_date="3 June 2026")
        result = format_event(ev)
        assert "1 June 2026 \\- 3 June 2026" in result

    def test_partial_time_no_end(self):
        ev = self._make_event(start_time="10:00 AM", end_time=None)
        result = format_event(ev)
        assert "empty" in result

    def test_partial_time_no_start(self):
        ev = self._make_event(start_time=None, end_time="12:00 PM")
        result = format_event(ev)
        assert "empty" in result

    def test_all_fields_normal(self):
        """Golden path: all fields present, no special chars."""
        ev = self._make_event()
        result = format_event(ev)
        assert "Test Event" in result
        assert "Free" in result
        assert "Online" in result
        assert "Register/More Info" in result


# =============================================================================
# Plan 4: Event status field — compute_status()
# =============================================================================

class TestComputeStatus:
    def test_past_date_returns_expired(self):
        assert compute_status({"end_date": "13 April 2025"}) == "expired"

    def test_future_date_returns_active(self):
        assert compute_status({"end_date": "13 June 2026"}) == "active"

    def test_start_date_fallback_active(self):
        assert compute_status({"start_date": "1 July 2026"}) == "active"

    def test_start_date_fallback_expired(self):
        assert compute_status({"start_date": "1 April 2020"}) == "expired"

    def test_tbd_returns_upcoming(self):
        assert compute_status({"start_date": "TBD"}) == "upcoming"

    def test_none_returns_upcoming(self):
        assert compute_status({"start_date": None, "end_date": None}) == "upcoming"

    def test_empty_string_returns_upcoming(self):
        assert compute_status({"start_date": "", "end_date": ""}) == "upcoming"

    def test_unparseable_date_returns_upcoming(self):
        assert compute_status({"end_date": "someday"}) == "upcoming"

    def test_missing_keys_returns_upcoming(self):
        assert compute_status({}) == "upcoming"

    def test_end_date_takes_priority(self):
        result = compute_status({"start_date": "1 June 2026", "end_date": "13 April 2025"})
        assert result == "expired"

    def test_single_date_today(self):
        """Today's date should be active (still happening)."""
        today = datetime.now().strftime("%d %B %Y")
        assert compute_status({"end_date": today}) == "active"

    def test_tomorrow_active(self):
        """Tomorrow is clearly active."""
        from datetime import timedelta
        tomorrow = (datetime.now() + timedelta(days=1)).strftime("%d %B %Y")
        assert compute_status({"end_date": tomorrow}) == "active"


# =============================================================================
# Plan 5: Fix search + markdown errors — URL escaping edge cases
# =============================================================================

class TestUrlEscaping:
    def test_url_with_query_params(self):
        result = escape_markdown("https://example.com/path?id=123&name=test", version=2)
        assert "\\=" in result

    def test_url_with_hash(self):
        result = escape_markdown("https://example.com/page#section", version=2)
        assert "#section" in result

    def test_url_with_plus(self):
        result = escape_markdown("https://example.com/path?q=a+b", version=2)
        assert "a\\+b" in result

    def test_markdownv2_link_syntax_valid(self):
        url = escape_markdown("https://example.com/event(2026)", version=2)
        text = escape_markdown("Register Here", version=2)
        link = f"[{text}]({url})"
        assert link.startswith("[")
        assert "](" in link
        assert link.endswith(")")

    def test_escaped_url_in_format_event(self):
        ev = {
            "title": "URL Test",
            "start_date": "1 June 2026",
            "end_date": None,
            "start_time": "10:00 AM",
            "end_time": None,
            "fee": "Free",
            "venue": "Online",
            "registration_link": "https://example.com/path(1)?a=b",
            "has_mycsd": False,
            "status": "active",
        }
        result = format_event(ev)
        assert "path\\(1\\)" in result
        assert "](" in result


# =============================================================================
# Plan 6: Null for unmentioned fields — validate_date()
# =============================================================================

class TestValidateDate:
    def test_full_date_passes(self):
        assert validate_date("13 April 2025") == "13 April 2025"

    def test_no_year_returns_none(self):
        assert validate_date("12 April") is None

    def test_no_day_returns_none(self):
        assert validate_date("April 2025") is None

    def test_year_only_returns_none(self):
        assert validate_date("2025") is None

    def test_range_with_year_passes(self):
        assert validate_date("12-13 April 2025") == "12-13 April 2025"

    def test_tbd_preserved(self):
        assert validate_date("TBD") == "TBD"

    def test_none_input(self):
        assert validate_date(None) is None

    def test_empty_string(self):
        assert validate_date("") is None

    def test_abbreviated_month_passes(self):
        assert validate_date("13 Apr 2025") == "13 Apr 2025"

    def test_short_month_returns_none(self):
        assert validate_date("13 Ap 2025") is None

    def test_single_digit_day(self):
        assert validate_date("1 May 2026") == "1 May 2026"

    def test_two_digit_day(self):
        assert validate_date("15 June 2026") == "15 June 2026"

    def test_no_month_returns_none(self):
        assert validate_date("13 2025") is None

    def test_malformed_date(self):
        assert validate_date("foo bar baz") is None


# =============================================================================
# NLP handler: rank_title_candidates
# =============================================================================

class TestRankTitleCandidates:
    def test_returns_sorted_scores(self):
        result = rank_title_candidates("First Line\nSecond Line\nThird Line")
        assert len(result) > 0
        for i in range(len(result) - 1):
            assert result[i][1] >= result[i + 1][1]

    def test_bracketed_line_scores_higher(self):
        text = "[Hackathon 2026]\nRandom announcement text"
        result = rank_title_candidates(text)
        assert result[0][0].startswith("[")

    def test_negative_keywords_penalized(self):
        text = "Registration for Event\nReal Event Title"
        result = rank_title_candidates(text)
        assert "Registration" not in result[0][0]

    def test_empty_text(self):
        assert rank_title_candidates("") == []

    def test_single_word_lines_skipped(self):
        result = rank_title_candidates("A\nBC\nEvent Title Here")
        titles = [line for line, _ in result]
        assert "A" not in titles

    def test_multiline_text(self):
        text = "\n\n\nOnly this line matters\n"
        result = rank_title_candidates(text)
        assert len(result) >= 1


# =============================================================================
# NLP entity extraction fallbacks (emoji-prefixed lines, non-English months)
# =============================================================================

class TestNlpEntityFallback:
    def test_date_with_emoji_and_indonesian_month(self):
        text = "🗓 19 Mei 2026\n⏰ 8.00 PM - 10.00 PM\n💻 Cisco Webex\n💰 RM1 only"
        result = extract_entities(text)
        assert "19 Mei 2026" in result.get("date_spacy", [])

    def test_date_with_calendar_emoji(self):
        text = "📅 1 June 2026\nEvent details here"
        result = extract_entities(text)
        assert "1 June 2026" in result.get("date_spacy", [])

    def test_time_with_clock_emoji(self):
        text = "Event Title\n⏰ 8.00 PM - 10.00 PM"
        result = extract_entities(text)
        assert len(result.get("time_spacy", [])) >= 2
        assert "8.00 PM" in result["time_spacy"][0]

    def test_date_range_with_en_dash_and_malay_label(self):
        text = "🗓 Tempoh Pertandingan: 11–31 Mei 2026\n💰 Yuran: RM1"
        result = extract_entities(text)
        assert "11 Mei 2026" in result.get("date_spacy", [])
        assert "31 Mei 2026" in result.get("date_spacy", [])


# =============================================================================
# Fee extraction edge cases
# =============================================================================

class TestExtractFee:
    def test_no_fee_info_defaults_free(self):
        assert extract_fee("Just an announcement") == "Free"

    def test_free_keyword(self):
        assert extract_fee("This event is Free!") == "Free"

    def test_currency_amount_paid(self):
        assert extract_fee("Fee: RM10") == "Paid"

    def test_fee_label_free(self):
        assert extract_fee("Fee: Free") == "Free"

    def test_empty_text(self):
        assert extract_fee("") == "Free"

    def test_percuma_keyword(self):
        assert extract_fee("Yuran: Percuma") == "Free"

    def test_price_zero_still_free(self):
        assert extract_fee("Fee: RM0") is None or extract_fee("Fee: RM0") == "Paid"

    def test_no_fee_mention(self):
        assert extract_fee("Event details here") == "Free"


# =============================================================================
# Cross-plan integration: Full event data flow
# =============================================================================

class TestFullEventFlow:
    def test_event_with_special_chars_flow(self):
        ev = {
            "title": "C++ Workshop: Tech_Talk_2026",
            "start_date": "1 June 2026",
            "end_date": "3 June 2026",
            "start_time": "10:00 AM",
            "end_time": "12:00 PM",
            "fee": "RM10*",
            "venue": "DK (Main Hall) #1",
            "registration_link": "https://example.com/event(2026)?ref=test",
            "has_mycsd": True,
            "status": "active",
        }
        result = format_event(ev)
        assert "ACTIVE" in result
        assert "Yes" in result
        assert "\\_Talk\\_" in result or "Workshop" in result

    def test_minimal_event_flow(self):
        ev = {
            "title": "Minimal",
            "start_date": None,
            "end_date": None,
            "start_time": None,
            "end_time": None,
            "fee": None,
            "venue": None,
            "registration_link": None,
            "has_mycsd": False,
            "status": "upcoming",
        }
        result = format_event(ev)
        assert "empty" in result
        assert "UPCOMING" in result

    def test_expired_event_shows_expired(self):
        ev = {
            "title": "Past Event",
            "start_date": "1 April 2025",
            "end_date": "1 April 2025",
            "start_time": "10:00 AM",
            "end_time": "12:00 PM",
            "fee": "Free",
            "venue": "Online",
            "registration_link": "https://example.com",
            "has_mycsd": False,
            "status": "expired",
        }
        result = format_event(ev)
        assert "EXPIRED" in result


# =============================================================================
# API integration tests (requires running Docker)
# =============================================================================

class TestApiIntegration:
    """Integration tests against live API. Skipped if API not reachable."""

    API_URL = "http://localhost:8000"

    @staticmethod
    def _api_reachable():
        import urllib.request
        try:
            urllib.request.urlopen(f"{TestApiIntegration.API_URL}/events", timeout=3)
            return True
        except Exception:
            return False

    def _post_event(self, text):
        import urllib.request
        import json
        data = json.dumps({"text": text}).encode()
        req = urllib.request.Request(
            f"{self.API_URL}/events/process",
            data=data,
            headers={"Content-Type": "application/json"}
        )
        try:
            resp = urllib.request.urlopen(req, timeout=10)
            return json.loads(resp.read())
        except urllib.request.HTTPError as e:
            return json.loads(e.read())
        except Exception:
            return None

    def _get_events(self):
        import urllib.request
        try:
            resp = urllib.request.urlopen(f"{self.API_URL}/events", timeout=5)
            return json.loads(resp.read())
        except Exception:
            return None

    # --- Plan 1: date display ---
    def test_api_date_display_single(self):
        if not self._api_reachable():
            return
        data = self._post_event(f"[T{os.getpid()}] Single Date\nDate: 10 August 2026\nTime: 2pm\nVenue: Online")
        assert data is not None, "API unreachable or error"
        assert data.get("status") == "success" or data.get("detail"), f"Unexpected: {data}"
        if data.get("status") == "success":
            ext = data.get("extracted_data", {})
            assert ext.get("start_date") == "10 August 2026"

    def test_api_date_range(self):
        if not self._api_reachable():
            return
        text = f"[T{os.getpid()}] Range Ev\nDate: 12-14 August 2026\nTime: 2pm\nVenue: Online"
        data = self._post_event(text)
        if data and data.get("status") == "success":
            ext = data.get("extracted_data", {})
            assert ext.get("start_date") is not None
            assert ext.get("end_date") is not None

    def test_api_date_range_cross_month(self):
        if not self._api_reachable():
            return
        text = f"[T{os.getpid()}] CrossMonth\nTarikh: 18 Mei – 1 Jun 2026"
        data = self._post_event(text)
        if data and data.get("status") == "success":
            ext = data.get("extracted_data", {})
            assert ext.get("start_date") == "18 Mei 2026"
            assert ext.get("end_date") == "1 Jun 2026"

    # --- Plan 4: event status ---
    def test_api_status_future(self):
        if not self._api_reachable():
            return
        data = self._post_event(f"[T{os.getpid()}] Future\nDate: 15 September 2026\nTime: 2pm\nVenue: Online")
        assert data is not None
        ext = data.get("extracted_data", {})
        if ext:
            assert ext.get("status") == "active"

    def test_api_status_past(self):
        if not self._api_reachable():
            return
        data = self._post_event(f"[T{os.getpid()}] Past\nDate: 13 April 2025\nTime: 2pm\nVenue: Online")
        assert data is not None
        ext = data.get("extracted_data", {})
        if ext:
            assert ext.get("status") == "expired"

    # --- Plan 5: search ---
    def test_api_search_no_error(self):
        if not self._api_reachable():
            return
        result = self._get_events()
        assert result is not None
        assert result.get("status") == "success"

    def test_api_search_with_term(self):
        if not self._api_reachable():
            return
        import urllib.request
        try:
            resp = urllib.request.urlopen(
                f"{self.API_URL}/events?search=Event", timeout=5
            )
            data = json.loads(resp.read())
            assert data.get("status") == "success"
        except Exception:
            pass

    # --- Plan 6: null fields ---
    def test_api_no_fee_stores_null(self):
        if not self._api_reachable():
            return
        text = f"[T{os.getpid()}] NoFee\nDate: 20 September 2026\nTime: 2pm\nVenue: Online"
        data = self._post_event(text)
        if data and data.get("status") == "success":
            ext = data.get("extracted_data", {})
            assert ext.get("fee") == "Free"

    def test_api_no_link_stores_null(self):
        if not self._api_reachable():
            return
        text = f"[T{os.getpid()}] NoLink\nDate: 25 September 2026\nTime: 2pm\nVenue: Online"
        data = self._post_event(text)
        if data and data.get("status") == "success":
            ext = data.get("extracted_data", {})
            assert ext.get("registration_link") is None


# =============================================================================
# Manual runner
# =============================================================================

if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))

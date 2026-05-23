import sys
import os
import pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from api.engine.ai_handler import _build_prompt, _parse_response, _build_event_prompt, _parse_event_response, validate_event


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


class TestParseResponse:
    def test_valid_json(self):
        result = _parse_response('{"title": "Correct Title"}')
        assert result == "Correct Title"

    def test_whitespace_around_json(self):
        result = _parse_response('  {"title": "Workshop 2025"}  ')
        assert result == "Workshop 2025"

    def test_markdown_code_block(self):
        result = _parse_response('```json\n{"title": "Event Name"}\n```')
        assert result == "Event Name"

    def test_empty_title_returns_none(self):
        result = _parse_response('{"title": ""}')
        assert result is None

    def test_missing_title_field(self):
        result = _parse_response('{"other": "data"}')
        assert result is None

    def test_invalid_json(self):
        result = _parse_response("not json at all")
        assert result is None

    def test_none_input(self):
        result = _parse_response('{"title": null}')
        assert result is None


class TestBuildEventPrompt:
    def test_includes_candidates_raw_text_and_extracted(self):
        prompt = _build_event_prompt(
            ["Event Title", "Second Line"],
            "raw text body",
            {"date_raw": "1 June 2026", "time_raw": "2pm"}
        )
        assert "Event Title" in prompt
        assert "Second Line" in prompt
        assert "raw text body" in prompt
        assert "1 June 2026" in prompt
        assert "2pm" in prompt

    def test_includes_json_format_instruction(self):
        prompt = _build_event_prompt(["Title"], "text", {"date_raw": None, "time_raw": None})
        assert "title" in prompt
        assert "date" in prompt
        assert "time" in prompt
        assert "JSON" in prompt


class TestParseEventResponse:
    def test_valid_json_all_fields(self):
        result = _parse_event_response('{"title": "Event", "date": "1 June 2026", "time": "2pm"}')
        assert result == {"title": "Event", "date": "1 June 2026", "time": "2pm"}

    def test_empty_date_becomes_none(self):
        result = _parse_event_response('{"title": "Event", "date": "", "time": "2pm"}')
        assert result["date"] is None
        assert result["time"] == "2pm"

    def test_empty_time_becomes_none(self):
        result = _parse_event_response('{"title": "Event", "date": "1 June 2026", "time": ""}')
        assert result["date"] == "1 June 2026"
        assert result["time"] is None

    def test_missing_field_becomes_none(self):
        result = _parse_event_response('{"title": "Event"}')
        assert result["title"] == "Event"
        assert result["date"] is None
        assert result["time"] is None

    def test_whitespace_around_json(self):
        result = _parse_event_response('  {"title": "E", "date": "1 June 2026", "time": "2pm"}  ')
        assert result["title"] == "E"

    def test_invalid_json_returns_none(self):
        result = _parse_event_response("not json")
        assert result is None

    def test_null_values_returns_none(self):
        result = _parse_event_response('{"title": "E", "date": null, "time": null}')
        assert result["title"] == "E"
        assert result["date"] is None
        assert result["time"] is None


class TestValidateEventUnit:
    """Unit tests for validate_event that don't call real API."""

    @pytest.mark.asyncio
    async def test_no_api_key_returns_none(self, monkeypatch):
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        result = await validate_event(["Title"], "text", {"date_raw": None, "time_raw": None})
        assert result is None

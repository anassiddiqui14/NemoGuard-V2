"""
Unit tests for src/domain/agents/base_agent.py::_sanitize_and_parse_json.

Regression coverage for a real bug found while validating the WP-001
iteration-budget fix: Nemotron occasionally emits a JSON string value
containing a literal (unescaped) newline character instead of the required
`\\n` escape sequence -- most commonly in the Grounding Critic's
multi-sentence "feedback" field. The PREVIOUS "fix" for this
(`content.replace("\\n", "\\\\n"); content = content.replace("\\\\n", "\\n")`)
was a complete no-op that never actually escaped anything, so any response
containing a raw newline inside a string value still failed to parse with
"Invalid control character at: ...", silently degrading a genuinely
successful agent investigation into an error.
"""

import json
import pytest

from src.domain.agents.base_agent import _sanitize_and_parse_json


class TestSanitizeAndParseJson:
    def test_well_formed_json_parses_normally(self):
        raw = '{"a": 1, "b": "hello"}'
        assert _sanitize_and_parse_json(raw) == {"a": 1, "b": "hello"}

    def test_literal_newline_inside_string_value_is_escaped_and_parsed(self):
        # A raw newline embedded in a string value -- invalid per the JSON
        # spec, but something Nemotron produces in practice.
        raw = '{"feedback": "line one\nline two", "passed": true}'
        result = _sanitize_and_parse_json(raw)
        assert result == {"feedback": "line one\nline two", "passed": True}

    def test_multiple_literal_newlines_in_multiple_fields(self):
        raw = (
            '{"a": "first\nsecond\nthird", '
            '"b": "x\ny", '
            '"c": [1, 2, 3]}'
        )
        result = _sanitize_and_parse_json(raw)
        assert result["a"] == "first\nsecond\nthird"
        assert result["b"] == "x\ny"
        assert result["c"] == [1, 2, 3]

    def test_structural_whitespace_between_tokens_is_preserved(self):
        # Newlines OUTSIDE of string literals (i.e. pretty-printed JSON) are
        # legal and must not be touched/escaped -- only newlines INSIDE a
        # string literal are the problem.
        raw = '{\n  "a": 1,\n  "b": 2\n}'
        assert _sanitize_and_parse_json(raw) == {"a": 1, "b": 2}

    def test_already_escaped_newline_is_not_double_escaped(self):
        # A correctly-escaped \n (two chars: backslash, n) in the raw text
        # must remain a single actual newline after parsing -- not corrupted
        # into a literal backslash-n or double-escaped.
        raw = '{"a": "line one\\nline two"}'
        result = _sanitize_and_parse_json(raw)
        assert result["a"] == "line one\nline two"

    def test_carriage_return_and_tab_inside_string_are_escaped(self):
        raw = '{"a": "col1\tcol2\rend"}'
        result = _sanitize_and_parse_json(raw)
        assert result["a"] == "col1\tcol2\rend"

    def test_backslash_escaped_quote_inside_string_does_not_break_string_tracking(self):
        raw = '{"a": "she said \\"hi\\"\nand left"}'
        result = _sanitize_and_parse_json(raw)
        assert result["a"] == 'she said "hi"\nand left'

    def test_genuinely_invalid_json_still_raises(self):
        with pytest.raises(json.JSONDecodeError):
            _sanitize_and_parse_json('{"a": }')

    def test_previous_noop_bug_would_have_failed_this_case(self):
        """
        Regression guard: this exact input previously reproduced the real
        production failure ("LLM error: Invalid control character at: line 3
        column 49"). Confirms the fix actually resolves it end-to-end.
        """
        raw = (
            '{\n'
            '  "passed": true,\n'
            '  "feedback": "Independently verified the RCA finding.\n'
            'CloudWatch logs confirm the error.\n'
            'No contradicting evidence found.",\n'
            '  "final_plan": {"steps": []}\n'
            '}'
        )
        result = _sanitize_and_parse_json(raw)
        assert result["passed"] is True
        assert "CloudWatch logs confirm" in result["feedback"]

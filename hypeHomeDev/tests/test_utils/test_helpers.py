"""Tests for src.utils.helpers — utility functions."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from utils.helpers import (
    expand_path,
    format_timestamp,
    human_readable_size,
    safe_load_json,
)


class TestExpandPath:
    def test_tilde_expansion(self):
        result = expand_path("~/some/dir")
        assert not str(result).startswith("~")
        assert result.is_absolute()

    def test_already_absolute(self):
        result = expand_path("/tmp/test")
        assert result == Path("/tmp/test")


class TestSafeLoadJson:
    def test_valid_json(self, tmp_path):
        p = tmp_path / "data.json"
        p.write_text(json.dumps({"key": "value"}))
        assert safe_load_json(p) == {"key": "value"}

    def test_invalid_json(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text("NOT JSON")
        assert safe_load_json(p, default={}) == {}

    def test_missing_file(self, tmp_path):
        p = tmp_path / "missing.json"
        assert safe_load_json(p) is None


class TestHumanReadableSize:
    def test_bytes(self):
        assert human_readable_size(500) == "500.0 B"

    def test_kibibytes(self):
        assert human_readable_size(1024) == "1.0 KiB"

    def test_mebibytes(self):
        assert human_readable_size(1024 * 1024) == "1.0 MiB"

    def test_gibibytes(self):
        assert human_readable_size(1024**3) == "1.0 GiB"

    def test_fractional(self):
        assert human_readable_size(1536) == "1.5 KiB"

    def test_zero(self):
        assert human_readable_size(0) == "0.0 B"


class TestFormatTimestamp:
    def test_default_uses_utc_now(self):
        result = format_timestamp()
        # Should be parseable without error.
        datetime.strptime(result, "%Y-%m-%d %H:%M:%S")

    def test_custom_datetime(self):
        dt = datetime(2025, 6, 15, 8, 30, 0, tzinfo=UTC)
        assert format_timestamp(dt) == "2025-06-15 08:30:00"

    def test_custom_format(self):
        dt = datetime(2025, 1, 1, tzinfo=UTC)
        assert format_timestamp(dt, fmt="%Y") == "2025"

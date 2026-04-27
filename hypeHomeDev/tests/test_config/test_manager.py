"""Tests for src.config.manager — ConfigManager."""

from __future__ import annotations

import json
import threading

import pytest

from config.manager import ConfigManager


@pytest.fixture()
def cfg(tmp_path):
    """Return a ConfigManager that writes to a temporary directory."""
    return ConfigManager(config_dir=tmp_path)


class TestConfigManager:
    def test_load_creates_default_file(self, cfg, tmp_path):
        cfg.load()
        config_file = tmp_path / "config.json"
        assert config_file.exists()
        data = json.loads(config_file.read_text())
        assert "theme" in data
        assert "refresh_interval" in data

    def test_get_returns_default(self, cfg):
        cfg.load()
        assert cfg.get("theme") == "system"
        assert cfg.get("refresh_interval") == 2.0
        assert cfg.get("nonexistent", "fallback") == "fallback"

    def test_set_persists(self, cfg, tmp_path):
        cfg.load()
        cfg.set("theme", "dark")
        assert cfg.get("theme") == "dark"
        # Read file to verify persistence.
        data = json.loads((tmp_path / "config.json").read_text())
        assert data["theme"] == "dark"

    def test_load_merges_stored_with_defaults(self, cfg, tmp_path):
        # Write a partial config file.
        (tmp_path / "config.json").write_text(json.dumps({"theme": "light"}))
        cfg.load()
        assert cfg.get("theme") == "light"
        # Default keys still present.
        assert cfg.get("refresh_interval") == 2.0

    def test_corrupt_json_resets_to_defaults(self, cfg, tmp_path):
        (tmp_path / "config.json").write_text("NOT VALID JSON!!!")
        cfg.load()
        assert cfg.get("theme") == "system"

    def test_as_dict_returns_copy(self, cfg):
        cfg.load()
        d = cfg.as_dict()
        d["theme"] = "changed"
        assert cfg.get("theme") != "changed"

    def test_thread_safety(self, cfg):
        """Smoke test: concurrent reads and writes should not crash."""
        cfg.load()
        errors: list[Exception] = []

        def writer():
            try:
                for i in range(50):
                    cfg.set("counter", i)
            except Exception as exc:
                errors.append(exc)

        def reader():
            try:
                for _ in range(50):
                    cfg.get("counter")
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=writer), threading.Thread(target=reader)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors

"""Process-service entries in services.json: sanitization and argv parsing."""

from __future__ import annotations

import shlex

from ui.widgets.workstation.service_manager import (
    _argv_binary_installed_probe,
    _argv_from_process_cmd,
    _load_service_catalog,
    _sanitize_process_service_entry,
)


def test_load_service_catalog_dropbox_process_cmds_intact() -> None:
    rows = _load_service_catalog()
    drop = next((r for r in rows if str(r.get("id")) == "dropbox"), None)
    assert drop is not None
    assert str(drop.get("kind")) == "process"
    assert drop.get("start_cmd") == "dropbox start"
    assert drop.get("stop_cmd") == "dropbox stop"
    assert drop.get("status_cmd") == "dropbox running"
    assert drop.get("binary") == "dropbox"


def test_sanitize_process_clears_injection_patterns() -> None:
    raw = {
        "id": "evil",
        "kind": "process",
        "binary": "dropbox",
        "start_cmd": "dropbox start; curl evil",
        "stop_cmd": "dropbox stop",
        "status_cmd": "echo $(id)",
    }
    clean = _sanitize_process_service_entry(raw)
    assert clean["start_cmd"] == ""
    assert clean["stop_cmd"] == "dropbox stop"
    assert clean["status_cmd"] == ""


def test_sanitize_process_rejects_bad_binary() -> None:
    raw = {
        "id": "badbin",
        "kind": "process",
        "binary": "foo; rm",
        "start_cmd": "true",
        "stop_cmd": "true",
        "status_cmd": "true",
    }
    clean = _sanitize_process_service_entry(raw)
    assert clean["binary"] == ""


def test_argv_from_process_cmd_parses_dropbox_lines() -> None:
    assert _argv_from_process_cmd("dropbox start") == ["dropbox", "start"]
    assert _argv_from_process_cmd("dropbox running") == ["dropbox", "running"]
    assert _argv_from_process_cmd("dropbox stop") == ["dropbox", "stop"]


def test_argv_from_process_cmd_rejects_shell() -> None:
    assert _argv_from_process_cmd("foo; bar") is None
    assert _argv_from_process_cmd("foo | bar") is None


def test_argv_binary_probe_quotes() -> None:
    argv = _argv_binary_installed_probe("docker-compose")
    assert argv is not None
    assert "command -v" in argv[2]
    assert shlex.quote("docker-compose") in argv[2]

"""Tests for Learn hub host probe argv construction."""

from __future__ import annotations

import shlex

from ui.widgets.workstation.learn_factory import argv_host_command_exists_probe


def test_argv_host_command_exists_probe_quotes_metacharacters() -> None:
    poison = "x; false; echo yes"
    argv = argv_host_command_exists_probe(poison)
    assert argv[:2] == ["sh", "-lc"]
    script = argv[2]
    quoted = shlex.quote(poison)
    assert quoted in script
    assert script.startswith("command -v ")


def test_argv_host_command_exists_probe_simple_program() -> None:
    argv = argv_host_command_exists_probe("docker")
    assert argv[0] == "sh"
    assert "docker" in argv[2]

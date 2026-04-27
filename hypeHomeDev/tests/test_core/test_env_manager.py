"""Tests for environment variable loading and managed file helpers."""

import pytest

from core.utils.env_manager import (
    EnvVarManager,
    parse_etc_environment,
    parse_shell_file,
)


def test_parse_etc_environment_basic():
    text = 'PATH="/usr/local/bin:/usr/bin"\nEDITOR=vim\n'
    pairs = parse_etc_environment(text)
    assert dict(pairs)["PATH"] == "/usr/local/bin:/usr/bin"
    assert dict(pairs)["EDITOR"] == "vim"


def test_parse_shell_export():
    text = "export FOO=bar\nexport BAR='baz qux'\n# comment\n"
    pairs = parse_shell_file(text)
    d = dict(pairs)
    assert d["FOO"] == "bar"
    assert d["BAR"] == "baz qux"


@pytest.mark.asyncio
async def test_env_manager_initializes_with_path():
    m = EnvVarManager()
    ok = await m.initialize()
    assert ok is True
    vars_ = m.get_variables()
    assert len(vars_) > 0
    assert any(v.key == "PATH" for v in vars_)

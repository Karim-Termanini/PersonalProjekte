"""Tests for Phase 9 PowerInstaller / outcome profiles."""

from __future__ import annotations

from dataclasses import fields

import pytest

from core.setup.host_executor import HostExecutor
from core.setup.power_installer import OutcomeProfile, PowerInstaller, _docker_run_argv


def test_outcome_profiles_load() -> None:
    ex = HostExecutor()
    pi = PowerInstaller(ex)
    profiles = pi.get_profiles()
    assert len(profiles) >= 1
    ids = {p.id for p in profiles}
    assert "python_ds" in ids
    assert "build_essentials" in ids
    assert "git_collab" in ids
    assert "terminal_essentials" in ids
    assert len(profiles) >= 6


def test_outcome_profile_json_ignores_unknown_keys() -> None:
    """Extra JSON keys must not break profile construction."""
    p = {
        "id": "test_extra",
        "name": "Test",
        "description": "d",
        "icon": "dialog-information-symbolic",
        "host_packages": [],
        "npm_packages": [],
        "services": [],
        "docker_containers": [],
        "ai_models": [],
        "future_field_should_be_ignored": True,
    }
    keys = {f.name for f in fields(OutcomeProfile)}
    prof = OutcomeProfile(**{k: v for k, v in p.items() if k in keys})
    assert prof.id == "test_extra"


@pytest.mark.asyncio
async def test_run_profile_unknown_returns_false() -> None:
    ex = HostExecutor()
    pi = PowerInstaller(ex)
    ok = await pi.run_profile("does-not-exist-zzz")
    assert ok is False


def test_docker_run_argv_env_and_volume() -> None:
    c = {
        "name": "t",
        "image": "redis:alpine",
        "ports": ["6379:6379"],
        "env": ["FOO=bar"],
        "volumes": ["volname:/data"],
    }
    argv = _docker_run_argv(c)
    assert argv is not None
    assert "redis:alpine" in argv
    assert "-e" in argv and "FOO=bar" in argv
    assert "-v" in argv and "volname:/data" in argv


@pytest.mark.asyncio
async def test_run_all_profiles_explicit_empty_noops() -> None:
    ex = HostExecutor()
    pi = PowerInstaller(ex)
    ok = await pi.run_all_profiles(profile_ids=[])
    assert ok is True


@pytest.mark.asyncio
async def test_run_all_profiles_unknown_ids_returns_false() -> None:
    ex = HostExecutor()
    pi = PowerInstaller(ex)
    ok = await pi.run_all_profiles(profile_ids=["__not_a_profile__"])
    assert ok is False


@pytest.mark.asyncio
async def test_run_all_profiles_invokes_each(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ex = HostExecutor()
    pi = PowerInstaller(ex)
    seen: list[str] = []

    async def fake_run(pid: str, _cb: object = None) -> bool:
        seen.append(pid)
        return True

    monkeypatch.setattr(pi, "run_profile", fake_run)
    ok = await pi.run_all_profiles()
    assert ok is True
    assert seen == [p.id for p in pi.get_profiles()]

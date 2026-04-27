"""Test logic in docker_manager helper functions."""

from __future__ import annotations

from ui.widgets.workstation.docker_manager import _docker_catalog_service


def test_docker_catalog_service_extraction() -> None:
    """Verify that _docker_catalog_service returns the correct dict from services.json."""
    data = _docker_catalog_service()
    
    assert isinstance(data, dict)
    assert data.get("id") == "docker"
    assert data.get("name") == "Docker"
    assert data.get("unit") == "docker.service"
    assert data.get("binary") == "docker"
    
    # Check that it extracted the description dictionary correctly
    desc = data.get("description")
    assert isinstance(desc, dict)
    assert "en" in desc
    assert "Container runtime and tooling" in desc["en"]

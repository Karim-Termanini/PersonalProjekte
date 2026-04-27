"""Docker cheatsheet: rendered by `learn_factory.py` + JSON data."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ui.widgets.workstation.learn_factory import WorkstationLearnFactoryPage


class DockerCheatsheetPage(WorkstationLearnFactoryPage):
    def __init__(self, **kwargs: Any) -> None:
        data_path = Path(__file__).with_name("data") / "docker.json"
        super().__init__(data_path=data_path, **kwargs)


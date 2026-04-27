import pytest

from core.setup.models import AppInfo
from core.setup.package_installer import PackageInstaller


class _DummyExecutor:
    def __init__(self, *, is_flatpak: bool) -> None:
        self.is_flatpak = is_flatpak


class _DummyManager:
    def __init__(self) -> None:
        self.removed: list[str] = []

    async def remove(self, package_id: str, progress_callback=None) -> bool:
        self.removed.append(package_id)
        return True


@pytest.mark.asyncio
async def test_remove_native_blocked_when_flatpak_host_access_off() -> None:
    executor = _DummyExecutor(is_flatpak=True)
    installer = PackageInstaller(executor, native_host_access=False)

    installer._initialized = True  # bypass initialize()
    dnf_manager = _DummyManager()
    flatpak_manager = _DummyManager()
    installer._package_managers = {"dnf": dnf_manager, "flatpak": flatpak_manager}

    native_app = AppInfo(
        id="dnf:pkg",
        name="Pkg",
        description="",
        icon="",
        package_name="pkg",
        category="dnf",
    )
    ok = await installer.remove_installed_app(native_app)
    assert ok is False
    assert dnf_manager.removed == []

    flatpak_app = AppInfo(
        id="flatpak:io.test.App",
        name="App",
        description="",
        icon="",
        package_name="ignored",
        flatpak_id="io.test.App",
        category="flatpak",
    )
    ok2 = await installer.remove_installed_app(flatpak_app)
    assert ok2 is True
    assert flatpak_manager.removed == ["io.test.App"]


"""HypeDevHome — Package Catalog.

Curated list of development tools with metadata for installation.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.setup.models import AppInfo

if TYPE_CHECKING:
    from core.setup.distro_detector import DistroInfo

log = logging.getLogger(__name__)


@dataclass
class PackageEntry:
    """Entry in the package catalog."""

    id: str
    name: str
    description: str
    category: str
    icon: str
    flatpak_id: str | None = None
    apt_package: str | None = None
    dnf_package: str | None = None
    pacman_package: str | None = None
    zypper_package: str | None = None
    snap_id: str | None = None
    homepage: str | None = None
    popularity: int = 0  # 0-100 scale


class PackageCatalog:
    """Manages the curated package catalog."""

    def __init__(self) -> None:
        self._packages: list[PackageEntry] = []
        self._categories: set[str] = set()
        self._loaded = False

    async def load(self) -> bool:
        """Load package catalog from JSON file."""
        if self._loaded:
            return True

        catalog_path = os.path.join(os.path.dirname(__file__), "package_catalog_data.json")
        try:
            with open(catalog_path) as f:
                data = json.load(f)

            self._packages = []
            self._categories = set()

            for item in data.get("packages", []):
                package = PackageEntry(
                    id=item["id"],
                    name=item["name"],
                    description=item["description"],
                    category=item["category"],
                    icon=item.get("icon", "application-x-executable-symbolic"),
                    flatpak_id=item.get("flatpak_id"),
                    apt_package=item.get("apt_package"),
                    dnf_package=item.get("dnf_package"),
                    pacman_package=item.get("pacman_package"),
                    zypper_package=item.get("zypper_package"),
                    snap_id=item.get("snap_id"),
                    homepage=item.get("homepage"),
                    popularity=item.get("popularity", 0),
                )
                self._packages.append(package)
                self._categories.add(package.category)

            self._loaded = True
            log.info("Loaded %d packages from catalog", len(self._packages))
            return True

        except Exception as e:
            log.error("Failed to load package catalog: %s", e)
            return False

    def get_all_packages(self) -> list[PackageEntry]:
        """Get all packages in the catalog."""
        if not self._loaded:
            log.warning("Package catalog not loaded, returning empty list")
            return []
        return self._packages.copy()

    def get_packages_by_category(self, category: str) -> list[PackageEntry]:
        """Get packages filtered by category."""
        if not self._loaded:
            return []
        return [p for p in self._packages if p.category == category]

    def get_categories(self) -> list[str]:
        """Get all available categories."""
        if not self._loaded:
            return []
        return sorted(self._categories)

    def search(self, query: str) -> list[PackageEntry]:
        """Search packages by name or description."""
        if not self._loaded:
            return []

        query = query.lower()
        results = []
        for package in self._packages:
            if (
                query in package.name.lower()
                or query in package.description.lower()
                or query in package.id.lower()
            ):
                results.append(package)
        return results

    def get_package(self, package_id: str) -> PackageEntry | None:
        """Get a specific package by ID."""
        if not self._loaded:
            return None

        for package in self._packages:
            if package.id == package_id:
                return package
        return None

    def get_package_for_distro(self, package_id: str, distro_info: DistroInfo) -> AppInfo | None:
        """Convert a PackageEntry to AppInfo for the current distribution."""
        package = self.get_package(package_id)
        if not package:
            return None

        # Determine the best package name for this distribution
        package_name = package.id  # Default to ID

        if distro_info.distro in ["ubuntu", "debian", "linuxmint"] and package.apt_package:
            package_name = package.apt_package
        elif distro_info.distro in ["fedora", "rhel", "centos"] and package.dnf_package:
            package_name = package.dnf_package
        elif distro_info.distro in ["arch", "manjaro"] and package.pacman_package:
            package_name = package.pacman_package
        elif distro_info.distro in ["opensuse", "suse"] and package.zypper_package:
            package_name = package.zypper_package

        # Create AppInfo
        return AppInfo(
            id=package.id,
            name=package.name,
            description=package.description,
            icon=package.icon,
            package_name=package_name,
            flatpak_id=package.flatpak_id,
            category=package.category,
        )

    def get_popular_packages(self, limit: int = 10) -> list[PackageEntry]:
        """Get the most popular packages."""
        if not self._loaded:
            return []

        sorted_packages = sorted(self._packages, key=lambda p: p.popularity, reverse=True)
        return sorted_packages[:limit]

    def get_packages_by_ids(self, package_ids: list[str]) -> list[PackageEntry]:
        """Get multiple packages by their IDs."""
        if not self._loaded:
            return []

        packages = []
        for package_id in package_ids:
            package = self.get_package(package_id)
            if package:
                packages.append(package)
        return packages

"""Hosts duplicate detection and parsing."""

from core.utils.hosts import (
    HostsEntry,
    duplicate_hostname_conflicts,
    parse_hosts_entries_from_lines,
)


def test_parse_hosts_basic():
    lines = ["127.0.0.1 localhost", "192.168.1.1 router.lan"]
    entries = parse_hosts_entries_from_lines(lines)
    assert len(entries) == 2
    assert entries[0].ip == "127.0.0.1"


def test_duplicate_hostname_conflicts():
    entries = [
        HostsEntry(ip="127.0.0.1", hostnames=["a.local"]),
        HostsEntry(ip="127.0.0.2", hostnames=["a.local"]),
    ]
    c = duplicate_hostname_conflicts(entries)
    assert len(c) >= 1

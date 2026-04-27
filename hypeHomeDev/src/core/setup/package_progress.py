"""Parse install/remove tool output lines for 0.0–1.0 progress."""

from __future__ import annotations

import re

# "45%", "100 %", "Progress: 12%"
_PCT = re.compile(r"(?:^|[^\d])(\d{1,3})\s*%")
# "3/10" or "Installing 3/10"
_FRAC = re.compile(r"(\d+)\s*/\s*(\d+)")
# DNF5 / rpm: "##########                                    ] 25%"
_HASHBAR = re.compile(r"\]\s*(\d{1,3})\s*%")
# Flatpak: "Installing 1/1…" with unicode bar sometimes includes percent
_FLATPAK_BYTES = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:KiB|MiB|GiB)\s*/\s*(\d+(?:\.\d+)?)\s*(?:KiB|MiB|GiB)",
    re.I,
)


def fraction_from_output_line(line: str) -> float | None:
    """Return monotonic-friendly progress 0.0–1.0, or None if no signal."""
    if not line or not line.strip():
        return None
    s = line.strip()

    m = _PCT.search(s)
    if m:
        v = int(m.group(1))
        if 0 <= v <= 100:
            return v / 100.0

    m = _HASHBAR.search(s)
    if m:
        v = int(m.group(1))
        if 0 <= v <= 100:
            return v / 100.0

    m = _FRAC.search(s)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        if b > 0 and a <= b:
            return min(1.0, a / b)

    m = _FLATPAK_BYTES.search(s)
    if m:
        # rough byte ratio (string compare of floats)
        try:
            cur = float(m.group(1))
            tot = float(m.group(2))
            if tot > 0:
                return min(1.0, cur / tot)
        except ValueError:
            pass

    return None

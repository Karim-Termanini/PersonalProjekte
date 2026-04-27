#!/usr/bin/env python3
"""Add metadata to system widgets."""

widgets = [
    ("cpu_widget.py", "CPU", "cpu-symbolic", "Shows CPU usage and temperature", "System"),
    ("gpu_widget.py", "GPU", "gpu-symbolic", "Shows GPU usage and temperature", "System"),
    ("memory_widget.py", "Memory", "ram-symbolic", "Shows RAM and swap usage", "System"),
    (
        "network_widget.py",
        "Network",
        "network-wired-symbolic",
        "Shows network speed and IP addresses",
        "System",
    ),
    ("ssh_widget.py", "SSH Keys", "key-symbolic", "Shows loaded SSH keys", "System"),
    ("clock_widget.py", "Clock", "clock-symbolic", "Shows current time", "Utilities"),
]

for filename, title, icon, description, category in widgets:
    with open(f"src/ui/widgets/{filename}") as f:
        content = f.read()

    # Find the class definition
    import re

    class_match = re.search(r"class (\w+)\s*\(.*?\):", content)
    if class_match:
        class_name = class_match.group(1)

        # Add metadata after class docstring
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if line.strip().startswith(f"class {class_name}"):
                # Find the next line after class definition
                for j in range(i + 1, len(lines)):
                    if lines[j].strip().startswith('"""') or lines[j].strip().startswith("'''"):
                        # Skip docstring
                        continue
                    if lines[j].strip() and not lines[j].strip().startswith("#"):
                        # Insert metadata before the first method/attribute
                        metadata = f'\n    # Metadata for widget gallery\n    widget_title = "{title}"\n    widget_icon = "{icon}"\n    widget_description = "{description}"\n    widget_category = "{category}"'
                        lines.insert(j, metadata)
                        break
                break

        new_content = "\n".join(lines)

        with open(f"src/ui/widgets/{filename}", "w") as f:
            f.write(new_content)

        print(f"Updated {filename}")

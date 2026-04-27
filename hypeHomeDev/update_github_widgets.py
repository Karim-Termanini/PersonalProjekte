#!/usr/bin/env python3
"""Add metadata to GitHub widgets."""

import re

widgets = [
    (
        "github_prs_widget.py",
        "GitHub Pull Requests",
        "git-pull-request-symbolic",
        "Shows your open GitHub pull requests",
    ),
    (
        "github_reviews_widget.py",
        "Review Requests",
        "user-available-symbolic",
        "Shows PRs awaiting your review",
    ),
    (
        "github_mentions_widget.py",
        "Mentioned Me",
        "chat-symbolic",
        "Shows issues/PRs where you were mentioned",
    ),
    (
        "github_assigned_widget.py",
        "Assigned to Me",
        "task-due-symbolic",
        "Shows issues assigned to you",
    ),
]

for filename, title, icon, description in widgets:
    with open(f"src/ui/widgets/{filename}") as f:
        content = f.read()

    # Find the class definition
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
                        metadata = f'\n    # Metadata for widget gallery\n    widget_title = "{title}"\n    widget_icon = "{icon}"\n    widget_description = "{description}"'
                        lines.insert(j, metadata)
                        break
                break

        new_content = "\n".join(lines)

        # Also update the __init__ title and icon if they're hardcoded
        new_content = re.sub(
            r'super\(\)\.__init__\(\s*title="[^"]*"',
            f'super().__init__(title="{title}"',
            new_content,
        )
        new_content = re.sub(r'icon_name="[^"]*"', f'icon_name="{icon}"', new_content)

        with open(f"src/ui/widgets/{filename}", "w") as f:
            f.write(new_content)

        print(f"Updated {filename}")

#!/usr/bin/env python3
"""Test widget creation timing to identify bottlenecks."""

import sys
import time
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))


def test_widget_creation_timing():
    """Test creation timing for each widget."""
    from ui.widgets.init_registry import register_built_in_widgets
    from ui.widgets.registry import WidgetRegistry

    # Register widgets once
    register_built_in_widgets()

    # Test each widget
    widgets_to_test = [
        "github_issues",
        "github_prs",
        "github_reviews",
        "github_mentions",
        "github_assigned",
    ]

    print("Widget Creation Timing Test (GitHub Widgets Only)")
    print("=" * 60)

    results = {}
    for widget_id in widgets_to_test:
        widget_class = WidgetRegistry.get_widget_class(widget_id)
        if widget_class:
            # Warm up (first creation might be slower due to imports)
            try:
                widget_class(widget_id=f"{widget_id}_test1")
            except Exception as e:
                print(f"Warning: Could not create {widget_id}_test1: {e}")

            # Time actual creation
            start_time = time.perf_counter()
            try:
                widget_class(widget_id=f"{widget_id}_test2")
                creation_time = (time.perf_counter() - start_time) * 1000  # ms
                results[widget_id] = creation_time
                print(f"{widget_id:20} {creation_time:8.2f} ms")
            except Exception as e:
                print(f"Error creating {widget_id}: {e}")

    print("\n" + "=" * 60)
    print("Analysis:")

    # Find slowest widgets
    sorted_results = sorted(results.items(), key=lambda x: x[1], reverse=True)
    print("\nSlowest widgets (>10ms):")
    for widget_id, time_ms in sorted_results:
        if time_ms > 10:
            print(f"  {widget_id}: {time_ms:.2f} ms")

    print("\nFastest widgets (<5ms):")
    for widget_id, time_ms in sorted_results:
        if time_ms < 5:
            print(f"  {widget_id}: {time_ms:.2f} ms")

    avg_time = sum(results.values()) / len(results) if results else 0
    print(f"\nAverage creation time: {avg_time:.2f} ms")

    return results


if __name__ == "__main__":
    test_widget_creation_timing()

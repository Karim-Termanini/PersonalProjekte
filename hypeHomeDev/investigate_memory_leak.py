#!/usr/bin/env python3
"""Investigate potential memory leaks in GitHub integration."""

import asyncio
import gc
import sys
import tracemalloc
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))


async def investigate_auth_manager() -> None:
    """Investigate auth manager for memory leaks."""
    print("\n" + "=" * 60)
    print("Investigating Auth Manager Memory Usage")
    print("=" * 60)

    from core.github.auth import get_auth_manager

    tracemalloc.start()

    # Create multiple instances (should be singleton)
    instances = []
    for i in range(10):
        auth = get_auth_manager()
        instances.append(auth)

        current, _peak = tracemalloc.get_traced_memory()
        print(f"  Instance {i + 1}: {current / 1024:.2f} KB")

    # Check if they're the same instance
    print(f"\nAll instances same object: {all(instances[0] is i for i in instances[1:])}")

    # Clear and force GC
    instances.clear()
    gc.collect()

    current, _peak = tracemalloc.get_traced_memory()
    print(f"After clearing: {current / 1024:.2f} KB")

    tracemalloc.stop()


async def investigate_api_client() -> None:
    """Investigate API client for memory leaks."""
    print("\n" + "=" * 60)
    print("Investigating API Client Memory Usage")
    print("=" * 60)

    from core.github.client import close_client, get_client

    tracemalloc.start()

    clients = []
    for i in range(5):
        client = await get_client()
        clients.append(client)

        current, _peak = tracemalloc.get_traced_memory()
        print(f"  Client {i + 1}: {current / 1024:.2f} KB")

    # Check if they're the same instance
    print(f"\nAll clients same object: {all(clients[0] is c for c in clients[1:])}")

    # Close all clients
    for _client in clients:
        await close_client()

    # Clear and force GC
    clients.clear()
    gc.collect()

    current, _peak = tracemalloc.get_traced_memory()
    print(f"After closing and clearing: {current / 1024:.2f} KB")

    tracemalloc.stop()


async def investigate_widget_registry() -> None:
    """Investigate widget registry for memory leaks."""
    print("\n" + "=" * 60)
    print("Investigating Widget Registry Memory Usage")
    print("=" * 60)

    from ui.widgets.init_registry import register_built_in_widgets
    from ui.widgets.registry import registry

    tracemalloc.start()

    # Register widgets multiple times
    for i in range(5):
        register_built_in_widgets()

        current, _peak = tracemalloc.get_traced_memory()
        print(f"  Registration {i + 1}: {current / 1024:.2f} KB")

    # Check registry size
    widget_ids = registry.list_widgets()
    print(f"\nTotal widgets registered: {len(widget_ids)}")

    # Force GC
    gc.collect()

    current, _peak = tracemalloc.get_traced_memory()
    print(f"After GC: {current / 1024:.2f} KB")

    tracemalloc.stop()


async def investigate_widget_creation() -> None:
    """Investigate widget creation for memory leaks."""
    print("\n" + "=" * 60)
    print("Investigating Widget Creation Memory Usage")
    print("=" * 60)

    from ui.widgets.init_registry import register_built_in_widgets
    from ui.widgets.registry import registry

    tracemalloc.start()

    # Register widgets once
    register_built_in_widgets()

    # Create and destroy widgets multiple times
    github_widgets = ["github_issues", "github_prs", "github_reviews"]

    all_widgets = []
    for cycle in range(3):
        print(f"\nCycle {cycle + 1}:")
        widgets = []

        for widget_id in github_widgets:
            widget_class = registry.get_widget_class(widget_id)
            if widget_class:
                widget = widget_class(widget_id=widget_id)
                widgets.append(widget)

        all_widgets.append(widgets)

        current, _peak = tracemalloc.get_traced_memory()
        print(f"  Created {len(widgets)} widgets: {current / 1024:.2f} KB")

    # Clear all widgets
    for widgets in all_widgets:
        widgets.clear()
    all_widgets.clear()

    # Force GC
    gc.collect()

    current, _peak = tracemalloc.get_traced_memory()
    print(f"\nAfter clearing all widgets and GC: {current / 1024:.2f} KB")

    tracemalloc.stop()


async def track_specific_objects() -> None:
    """Track specific object creation and destruction."""
    print("\n" + "=" * 60)
    print("Tracking Specific Object Lifecycle")
    print("=" * 60)

    import objgraph

    # Take initial snapshot
    print("Taking initial object snapshot...")

    from core.github.auth import get_auth_manager
    from core.github.client import close_client, get_client
    from ui.widgets.init_registry import register_built_in_widgets
    from ui.widgets.registry import registry

    # Create objects
    print("\nCreating objects...")
    auth = get_auth_manager()
    client = await get_client()
    register_built_in_widgets()

    # Create a widget
    widget_class = registry.get_widget_class("github_issues")
    widget = widget_class(widget_id="test_widget") if widget_class else None

    print(f"Auth object: {auth}")
    print(f"Client object: {client}")
    print(f"Widget object: {widget}")

    # Show most common types
    print("\nMost common object types:")
    try:
        objgraph.show_most_common_types(limit=10)
    except Exception as e:
        print(f"Could not show object graph: {e}")

    # Clean up
    print("\nCleaning up...")
    widget = None
    await close_client()

    # Force GC
    gc.collect()

    print("Cleanup complete.")


async def main() -> None:
    """Run all memory leak investigations."""
    print("=" * 60)
    print("Memory Leak Investigation")
    print("=" * 60)

    await investigate_auth_manager()
    await investigate_api_client()
    await investigate_widget_registry()
    await investigate_widget_creation()

    # Try to track specific objects (might fail without objgraph)
    try:
        await track_specific_objects()
    except ImportError:
        print("\nNote: Install 'objgraph' for detailed object tracking:")
        print("  pip install objgraph")

    print("\n" + "=" * 60)
    print("Investigation Complete")
    print("=" * 60)

    print("\nRecommendations:")
    print("1. The 'already registered' warnings suggest WidgetRegistry is not a proper singleton")
    print("2. Consider making WidgetRegistry a true singleton to avoid duplicate registrations")
    print("3. Implement __del__ methods for proper cleanup if needed")
    print("4. Use weak references for caches that should not prevent garbage collection")


if __name__ == "__main__":
    asyncio.run(main())

#!/usr/bin/env python3
"""Profile performance of GitHub integration components."""

import asyncio
import sys
import time
import tracemalloc
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))


async def profile_auth_manager() -> None:
    """Profile GitHub authentication manager performance."""
    print("\n" + "=" * 60)
    print("Profiling GitHub Authentication Manager")
    print("=" * 60)

    from core.github.auth import get_auth_manager

    tracemalloc.start()
    start_time = time.time()

    # Test auth manager initialization
    auth_manager = get_auth_manager()
    init_time = time.time() - start_time

    # Test authentication check
    start_time = time.time()
    auth_manager.is_authenticated()
    auth_check_time = time.time() - start_time

    # Test token validation (mock)
    start_time = time.time()
    test_token = "ghp_testtoken1234567890"
    _is_valid, _username, _scopes = auth_manager.validate_token(test_token)
    validation_time = time.time() - start_time

    # Memory usage
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    print(f"Initialization time: {init_time * 1000:.2f} ms")
    print(f"Auth check time: {auth_check_time * 1000:.2f} ms")
    print(f"Token validation time: {validation_time * 1000:.2f} ms")
    print(f"Current memory usage: {current / 1024:.2f} KB")
    print(f"Peak memory usage: {peak / 1024:.2f} KB")

    return {
        "init_time_ms": init_time * 1000,
        "auth_check_time_ms": auth_check_time * 1000,
        "validation_time_ms": validation_time * 1000,
        "memory_kb": current / 1024,
        "peak_memory_kb": peak / 1024,
    }


async def profile_api_client() -> None:
    """Profile GitHub API client performance."""
    print("\n" + "=" * 60)
    print("Profiling GitHub API Client")
    print("=" * 60)

    from core.github.client import close_client, get_client

    tracemalloc.start()

    # Test client initialization
    start_time = time.time()
    client = await get_client()
    init_time = time.time() - start_time

    # Test cache operations
    start_time = time.time()
    cache_size = len(client._cache)
    cache_time = time.time() - start_time

    # Test rate limit checking
    start_time = time.time()
    client.get_rate_limits()
    rate_limit_time = time.time() - start_time

    # Test closing client
    start_time = time.time()
    await close_client()
    close_time = time.time() - start_time

    # Memory usage
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    print(f"Client initialization time: {init_time * 1000:.2f} ms")
    print(f"Cache check time: {cache_time * 1000:.2f} ms")
    print(f"Rate limit check time: {rate_limit_time * 1000:.2f} ms")
    print(f"Client close time: {close_time * 1000:.2f} ms")
    print(f"Cache size: {cache_size} items")
    print(f"Current memory usage: {current / 1024:.2f} KB")
    print(f"Peak memory usage: {peak / 1024:.2f} KB")

    return {
        "init_time_ms": init_time * 1000,
        "cache_time_ms": cache_time * 1000,
        "rate_limit_time_ms": rate_limit_time * 1000,
        "close_time_ms": close_time * 1000,
        "cache_size": cache_size,
        "memory_kb": current / 1024,
        "peak_memory_kb": peak / 1024,
    }


async def profile_widget_creation() -> None:
    """Profile GitHub widget creation performance."""
    print("\n" + "=" * 60)
    print("Profiling GitHub Widget Creation")
    print("=" * 60)

    from ui.widgets.init_registry import register_built_in_widgets
    from ui.widgets.registry import WidgetRegistry

    tracemalloc.start()

    # Register widgets
    start_time = time.time()
    register_built_in_widgets()
    register_time = time.time() - start_time

    # Test creating each GitHub widget
    github_widgets = [
        "github_issues",
        "github_prs",
        "github_reviews",
        "github_mentions",
        "github_assigned",
    ]
    creation_times = []

    for widget_id in github_widgets:
        widget_class = WidgetRegistry.get_widget_class(widget_id)
        if widget_class:
            start_time = time.time()
            widget_class(widget_id=widget_id)
            creation_time = time.time() - start_time
            creation_times.append(creation_time)
            print(f"  {widget_id}: {creation_time * 1000:.2f} ms")

    avg_creation_time = sum(creation_times) / len(creation_times) if creation_times else 0

    # Memory usage
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    print(f"\nWidget registration time: {register_time * 1000:.2f} ms")
    print(f"Average widget creation time: {avg_creation_time * 1000:.2f} ms")
    print(f"Total widgets created: {len(github_widgets)}")
    print(f"Current memory usage: {current / 1024:.2f} KB")
    print(f"Peak memory usage: {peak / 1024:.2f} KB")

    return {
        "register_time_ms": register_time * 1000,
        "avg_creation_time_ms": avg_creation_time * 1000,
        "widgets_created": len(github_widgets),
        "memory_kb": current / 1024,
        "peak_memory_kb": peak / 1024,
    }


async def profile_concurrent_requests() -> None:
    """Profile concurrent API requests performance."""
    print("\n" + "=" * 60)
    print("Profiling Concurrent API Requests")
    print("=" * 60)

    from core.github.client import close_client, get_client

    tracemalloc.start()

    # Get client
    await get_client()

    # Simulate concurrent requests (mocked)
    async def mock_request(i: int) -> dict:
        await asyncio.sleep(0.01)  # Simulate network delay
        return {"request_id": i, "status": "success"}

    # Test with different concurrency levels
    results = {}
    for concurrency in [1, 3, 5]:
        print(f"\nTesting with {concurrency} concurrent requests:")

        start_time = time.time()
        tasks = [mock_request(i) for i in range(concurrency)]
        await asyncio.gather(*tasks)
        total_time = time.time() - start_time

        avg_time = total_time / concurrency
        print(f"  Total time: {total_time * 1000:.2f} ms")
        print(f"  Average per request: {avg_time * 1000:.2f} ms")

        results[concurrency] = {
            "total_time_ms": total_time * 1000,
            "avg_time_ms": avg_time * 1000,
        }

    # Close client
    await close_client()

    # Memory usage
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    print(f"\nCurrent memory usage: {current / 1024:.2f} KB")
    print(f"Peak memory usage: {peak / 1024:.2f} KB")

    return {
        "concurrent_results": results,
        "memory_kb": current / 1024,
        "peak_memory_kb": peak / 1024,
    }


async def profile_memory_leaks() -> None:
    """Profile for memory leaks in GitHub components."""
    print("\n" + "=" * 60)
    print("Profiling for Memory Leaks")
    print("=" * 60)

    import gc

    from core.github.auth import get_auth_manager
    from core.github.client import close_client, get_client
    from ui.widgets.init_registry import register_built_in_widgets
    from ui.widgets.registry import WidgetRegistry

    # Force garbage collection
    gc.collect()

    # Track initial memory
    tracemalloc.start()
    initial_current, _initial_peak = tracemalloc.get_traced_memory()

    # Create and destroy objects multiple times
    iterations = 10
    memory_samples = []

    for i in range(iterations):
        # Create objects
        get_auth_manager()
        await get_client()
        register_built_in_widgets()

        # Create some widgets
        github_widgets = ["github_issues", "github_prs", "github_reviews"]
        widgets = []
        for widget_id in github_widgets:
            widget_class = WidgetRegistry.get_widget_class(widget_id)
            if widget_class:
                widget = widget_class(widget_id=widget_id)
                widgets.append(widget)

        # Get memory usage
        current, _peak = tracemalloc.get_traced_memory()
        memory_samples.append(current)

        # Clean up
        widgets.clear()
        await close_client()

        # Force garbage collection
        gc.collect()

        if (i + 1) % 5 == 0:
            print(f"  Iteration {i + 1}/{iterations}: {current / 1024:.2f} KB")

    # Final memory
    final_current, final_peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    # Analyze memory growth
    memory_growth = final_current - initial_current
    max_memory = max(memory_samples) if memory_samples else 0

    print(f"\nInitial memory: {initial_current / 1024:.2f} KB")
    print(f"Final memory: {final_current / 1024:.2f} KB")
    print(f"Memory growth: {memory_growth / 1024:.2f} KB")
    print(f"Max memory during test: {max_memory / 1024:.2f} KB")
    print(f"Peak memory overall: {final_peak / 1024:.2f} KB")

    if memory_growth > 1024:  # More than 1KB growth
        print("⚠️  WARNING: Possible memory leak detected!")
    else:
        print("✅ No significant memory leaks detected.")

    return {
        "initial_memory_kb": initial_current / 1024,
        "final_memory_kb": final_current / 1024,
        "memory_growth_kb": memory_growth / 1024,
        "max_memory_kb": max_memory / 1024,
        "peak_memory_kb": final_peak / 1024,
        "has_leak": memory_growth > 1024,
    }


async def main() -> None:
    """Run all performance profiling tests."""
    print("=" * 60)
    print("GitHub Integration Performance Profiling")
    print("=" * 60)

    results = {}

    # Run all profiling tests
    results["auth_manager"] = await profile_auth_manager()
    results["api_client"] = await profile_api_client()
    results["widget_creation"] = await profile_widget_creation()
    results["concurrent_requests"] = await profile_concurrent_requests()
    results["memory_leaks"] = await profile_memory_leaks()

    # Summary
    print("\n" + "=" * 60)
    print("PERFORMANCE SUMMARY")
    print("=" * 60)

    # Calculate overall performance metrics
    total_init_time = (
        results["auth_manager"]["init_time_ms"]
        + results["api_client"]["init_time_ms"]
        + results["widget_creation"]["register_time_ms"]
    )

    avg_widget_time = results["widget_creation"]["avg_creation_time_ms"]

    total_memory = sum(
        [
            results["auth_manager"]["memory_kb"],
            results["api_client"]["memory_kb"],
            results["widget_creation"]["memory_kb"],
        ]
    )

    print(f"Total initialization time: {total_init_time:.2f} ms")
    print(f"Average widget creation time: {avg_widget_time:.2f} ms")
    print(f"Estimated total memory usage: {total_memory:.2f} KB")
    print(f"Memory leak detected: {'Yes' if results['memory_leaks']['has_leak'] else 'No'}")

    # Performance recommendations
    print("\n" + "=" * 60)
    print("PERFORMANCE RECOMMENDATIONS")
    print("=" * 60)

    if total_init_time > 100:
        print("⚠️  Initialization time is high (>100ms). Consider lazy loading.")

    if avg_widget_time > 50:
        print("⚠️  Widget creation time is high (>50ms). Consider caching widget instances.")

    if total_memory > 5000:
        print("⚠️  Memory usage is high (>5MB). Consider memory optimization.")

    if not results["memory_leaks"]["has_leak"]:
        print("✅ Memory management is good - no significant leaks detected.")

    print("\n" + "=" * 60)
    print("Performance profiling complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

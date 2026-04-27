#!/usr/bin/env python3
"""Test script for StackManager functionality."""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from core.setup.environments import EnvironmentManager
from core.setup.host_executor import HostExecutor
from core.setup.stack_manager import StackManager


async def test_stack_manager():
    """Test StackManager functionality."""
    print("🧪 Testing StackManager...")

    # Initialize components
    executor = HostExecutor()
    env_manager = EnvironmentManager(executor)
    stack_manager = StackManager(executor, env_manager)

    # Test 1: Load catalog
    print("\n1. Testing catalog loading...")
    stacks = stack_manager.get_available_stacks()
    print(f"   Loaded {len(stacks)} stack templates:")
    for stack in stacks:
        print(f"   - {stack.name} ({stack.id}): {stack.description}")

    # Test 2: Get specific stack
    print("\n2. Testing stack retrieval...")
    python_stack = stack_manager.get_stack("python_ds")
    if python_stack:
        print(f"   Found Python stack: {python_stack.name}")
        print(f"   Packages: {', '.join(python_stack.packages[:3])}...")
        print(f"   Exports: {', '.join(python_stack.exports)}")
    else:
        print("   ERROR: Python stack not found!")

    # Test 3: Check environment detection
    print("\n3. Testing environment detection...")
    await env_manager.initialize()
    print(f"   Distrobox available: {env_manager.has_distrobox}")
    print(f"   Toolbx available: {env_manager.has_toolbx}")
    print(f"   Podman available: {env_manager.has_podman}")
    print(f"   Docker available: {env_manager.has_docker}")

    # Test 4: List running environments
    print("\n4. Testing environment listing...")
    envs = await env_manager.list_environments()
    print(f"   Found {len(envs)} existing environments:")
    for env in envs:
        print(f"   - {env}")

    # Test 5: Test container engine availability
    print("\n5. Testing container engine...")
    if await env_manager.ensure_container_engine():
        print("   ✓ Container engine is available")
    else:
        print("   ✗ No container engine available")

    # Test 6: Test stack status methods
    print("\n6. Testing stack status methods...")
    if stacks:
        test_stack = stacks[0]
        status = await stack_manager.get_stack_status(test_stack.id)
        print(f"   Status for {test_stack.id}:")
        print(f"     Exists: {status['exists']}")
        print(f"     Running: {status['running']}")

    print("\n✅ StackManager tests completed!")
    print("\nNote: To test actual container creation, run:")
    print("  python -m pytest tests/test_core/test_distrobox_stacks.py")


if __name__ == "__main__":
    asyncio.run(test_stack_manager())

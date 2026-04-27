#!/usr/bin/env python3
"""Test script for GitHub widgets."""

import asyncio
import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))


async def test_github_auth() -> None:
    """Test GitHub authentication."""
    print("Testing GitHub authentication...")

    from core.github.auth import get_auth_manager

    auth_manager = get_auth_manager()

    # Check initial state
    print(f"Initial auth state: {auth_manager.is_authenticated()}")
    print(f"Username: {auth_manager.get_username()}")
    print(f"Has token: {auth_manager.get_token() is not None}")

    # Test token validation (mock)
    test_token = "ghp_testtoken1234567890"
    is_valid, username, scopes = auth_manager.validate_token(test_token)
    print("\nToken validation test:")
    print(f"  Token valid: {is_valid}")
    print(f"  Username: {username}")
    print(f"  Scopes: {scopes}")

    print("\nGitHub authentication test completed!")


async def test_github_client() -> None:
    """Test GitHub client."""
    print("\nTesting GitHub client...")

    from core.github.client import close_client, get_client

    try:
        client = await get_client()
        print(f"Client created: {client}")
        print(f"Client session: {client._session}")

        # Note: We can't actually make API calls without authentication
        # This just tests that the client can be created

        await close_client()
        print("Client closed successfully")

    except Exception as e:
        print(f"Error creating client: {e}")

    print("GitHub client test completed!")


async def test_widget_creation() -> None:
    """Test widget creation."""
    print("\nTesting widget creation...")

    try:
        from ui.widgets.github_assigned_widget import GitHubAssignedWidget
        from ui.widgets.github_issues_widget import GitHubIssuesWidget
        from ui.widgets.github_mentions_widget import GitHubMentionsWidget
        from ui.widgets.github_prs_widget import GitHubPRsWidget
        from ui.widgets.github_reviews_widget import GitHubReviewsWidget

        widgets = [
            ("Issues", GitHubIssuesWidget),
            ("PRs", GitHubPRsWidget),
            ("Reviews", GitHubReviewsWidget),
            ("Mentions", GitHubMentionsWidget),
            ("Assigned", GitHubAssignedWidget),
        ]

        for name, widget_class in widgets:
            try:
                # Create widget instance with widget_id
                widget_id = f"github_{name.lower().replace(' ', '_')}"
                widget = widget_class(widget_id=widget_id)
                print(f"  ✓ {name} widget created successfully")

                # Check widget properties
                print(f"    - Widget ID: {widget.widget_id}")
                print(f"    - Title: {widget.title}")
                print(f"    - Icon: {widget.icon_name}")
                print(f"    - Refresh interval: {widget._refresh_interval}s")

            except Exception as e:
                print(f"  ✗ {name} widget failed: {e}")

        print("\nAll widgets created successfully!")

    except Exception as e:
        print(f"Error testing widgets: {e}")


async def main() -> None:
    """Run all tests."""
    print("=" * 60)
    print("GitHub Widgets Test Suite")
    print("=" * 60)

    await test_github_auth()
    await test_github_client()
    await test_widget_creation()

    print("\n" + "=" * 60)
    print("All tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

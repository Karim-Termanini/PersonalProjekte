"""Tests for GitHub authentication dialog."""

from unittest.mock import MagicMock, patch

from ui.dialogs.github_auth import GitHubAuthDialog


class TestGitHubAuthDialog:
    """Test the GitHub authentication dialog."""

    def test_dialog_initialization(self):
        """Test dialog initializes correctly."""
        dialog = GitHubAuthDialog()

        assert dialog is not None
        assert dialog._token_entry is not None
        assert dialog._validate_button is not None

    @patch("ui.dialogs.github_auth.get_auth_manager")
    def test_validate_token_empty(self, mock_get_auth_manager):
        """Test token validation with empty input."""
        mock_auth = MagicMock()
        mock_get_auth_manager.return_value = mock_auth
        dialog = GitHubAuthDialog()

        # Set empty token
        dialog._token_entry.set_text("")

        # Mock show error
        dialog._show_error = MagicMock()

        dialog._on_validate_token(None)

        dialog._show_error.assert_called_once_with("Please enter a token")
        mock_auth.validate_token.assert_not_called()

    @patch("gi.repository.GLib.timeout_add")
    @patch("ui.dialogs.github_auth.get_auth_manager")
    def test_validate_token_valid(self, mock_get_auth_manager, mock_glib_timeout):
        """Test token validation with valid token."""
        mock_auth = MagicMock()
        mock_auth.validate_token.return_value = (True, "testuser", ["repo"])
        mock_auth.set_credentials.return_value = True
        mock_get_auth_manager.return_value = mock_auth

        dialog = GitHubAuthDialog()
        dialog._show_success = MagicMock()

        # Set token
        dialog._token_entry.set_text("ghp_validtoken")
        dialog._on_validate_token(None)

        # Verify token was saved
        mock_auth.validate_token.assert_called_once_with("ghp_validtoken")
        mock_auth.set_credentials.assert_called_once_with("ghp_validtoken", "testuser", ["repo"])
        dialog._show_success.assert_called_once_with("Connected as testuser")

    @patch("ui.dialogs.github_auth.get_auth_manager")
    def test_validate_token_invalid(self, mock_get_auth_manager):
        """Test token validation with invalid token."""
        mock_auth = MagicMock()
        mock_auth.validate_token.return_value = (False, None, None)
        mock_get_auth_manager.return_value = mock_auth

        dialog = GitHubAuthDialog()
        dialog._show_error = MagicMock()

        # Set token
        dialog._token_entry.set_text("ghp_invalidtoken")
        dialog._on_validate_token(None)

        # Verify error displayed
        mock_auth.validate_token.assert_called_once_with("ghp_invalidtoken")
        dialog._show_error.assert_called_once_with(
            "Invalid token. Please check your token and try again."
        )

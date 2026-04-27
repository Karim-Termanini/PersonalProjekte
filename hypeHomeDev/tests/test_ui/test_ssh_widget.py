"""HypeDevHome — Tests for the SSHWidget."""

from __future__ import annotations

import os
from unittest.mock import Mock, patch

from ui.widgets.ssh_widget import SSHKey, SSHWidget


def test_ssh_key_creation() -> None:
    key = SSHKey(fingerprint="SHA256:abc123", comment="test@host", key_path="/path/to/key")
    assert key.fingerprint == "SHA256:abc123"
    assert key.comment == "test@host"
    assert key.key_path == "/path/to/key"
    assert "SHA256:abc123" in str(key)


def test_ssh_widget_instantiates() -> None:
    widget = SSHWidget()
    assert widget is not None
    assert widget.widget_id == "ssh"
    assert hasattr(widget, "_keys")
    assert isinstance(widget._keys, list)
    assert widget.widget_title == "SSH Keys"
    assert widget.widget_icon == "key-symbolic"
    assert widget.widget_description == "Monitor and manage SSH keys loaded in ssh-agent"
    assert widget.widget_category == "System"


def test_ssh_key_type_detection() -> None:
    widget = SSHWidget()

    # Test RSA key detection
    assert widget._get_key_type("SHA256:abc123 (RSA)") == "RSA"

    # Test ECDSA key detection
    assert widget._get_key_type("SHA256:def456 (ECDSA)") == "ECDSA"

    # Test Ed25519 key detection
    assert widget._get_key_type("SHA256:ghi789 (ED25519)") == "Ed25519"

    # Test unknown key type
    assert widget._get_key_type("SHA256:jkl012") == "RSA/ECDSA/Ed25519"


def test_ssh_key_icon_mapping() -> None:
    widget = SSHWidget()

    assert widget._get_key_icon("RSA") == "security-high-symbolic"
    assert widget._get_key_icon("ECDSA") == "security-medium-symbolic"
    assert widget._get_key_icon("Ed25519") == "security-low-symbolic"
    assert widget._get_key_icon("RSA/ECDSA/Ed25519") == "key-symbolic"
    assert widget._get_key_icon("Unknown") == "key-symbolic"


def test_ssh_widget_config() -> None:
    widget = SSHWidget()
    config = widget.get_config()

    assert "id" in config
    assert config["id"] == "ssh"
    assert "agent_check_interval" in config
    assert isinstance(config["agent_check_interval"], float)


@patch.dict(os.environ, {"SSH_AUTH_SOCK": "/tmp/ssh-agent.sock"})
@patch("os.path.exists")
@patch("subprocess.run")
def test_ssh_agent_check_with_socket(mock_run, mock_exists):
    """Test SSH agent check when socket exists."""
    mock_exists.return_value = True
    mock_run.return_value = Mock(returncode=0, stdout="")

    widget = SSHWidget()
    widget._check_agent()

    assert widget._agent_socket == "/tmp/ssh-agent.sock"
    # Note: We can't fully test the UI updates without GTK initialization


@patch.dict(os.environ, {}, clear=True)
def test_ssh_agent_check_no_socket():
    """Test SSH agent check when no socket is set."""
    widget = SSHWidget()
    widget._check_agent()

    assert widget._agent_socket == ""
    assert not widget._agent_available

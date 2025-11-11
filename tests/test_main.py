"""
Tests for main.py orchestration functions
"""

from unittest.mock import Mock

import pytest

from automation.exceptions import GitHubError, KubernetesError
from automation.main import create_environment, delete_environment


@pytest.fixture
def mock_k8s_client():
    """Mock KubernetesClient with successful operations."""
    mock = Mock()
    mock.create_namespace.return_value = True
    mock.delete_namespace.return_value = True
    mock.create_deployment.return_value = True
    mock.create_service.return_value = True
    mock.create_middleware.return_value = True
    mock.create_ingress.return_value = True
    return mock


@pytest.fixture
def mock_github_client():
    """Mock GithubClient."""
    mock = Mock()
    mock.post_comment.return_value = True
    mock.update_comment.return_value = True
    mock.find_bot_comment.return_value = None
    return mock


@pytest.fixture
def test_config_file(tmp_path):
    """Create a temporary test config file."""
    config = tmp_path / "test-config.yaml"
    config.write_text(
        """
services:
  - name: frontend
    image: nginx:latest
    port: 80
    ingress:
      enabled: true
      path: "/"
  - name: backend
    image: node:latest
    port: 3000
    ingress:
      enabled: true
      path: "/api"
  - name: database
    image: postgres:latest
    port: 5432
"""
    )
    return str(config)


# ============================================================================
# CREATE ENVIRONMENT TESTS
# ============================================================================


def test_create_environment_success(mock_k8s_client, test_config_file, template_dir):
    """Test successful environment creation."""
    result = create_environment(
        k8s=mock_k8s_client,
        namespace="pr-999",
        config_path=test_config_file,
        template_dir=template_dir,
        github=None,
    )

    assert result is True
    mock_k8s_client.create_namespace.assert_called_once_with("pr-999")
    assert mock_k8s_client.create_deployment.call_count == 3
    assert mock_k8s_client.create_service.call_count == 3


def test_create_environment_with_github_comment_new(
    mock_k8s_client, mock_github_client, test_config_file, template_dir, monkeypatch
):
    """Test environment creation posts new GitHub comment."""
    monkeypatch.setenv("EC2_PUBLIC_IP", "1.2.3.4")

    mock_github_client.find_bot_comment.return_value = None

    result = create_environment(
        k8s=mock_k8s_client,
        namespace="pr-123",
        config_path=test_config_file,
        template_dir=template_dir,
        github=mock_github_client,
    )

    assert result is True

    mock_github_client.find_bot_comment.assert_called_once_with(123)
    mock_github_client.post_comment.assert_called_once()
    mock_github_client.update_comment.assert_not_called()

    call_args = mock_github_client.post_comment.call_args
    assert call_args[0][0] == 123
    message = call_args[0][1]
    assert "1.2.3.4" in message
    assert "pr-123" in message
    assert "Frontend:" in message
    assert "Backend:" in message


def test_create_environment_with_github_comment_update(
    mock_k8s_client, mock_github_client, test_config_file, template_dir, monkeypatch
):
    """Test that existing comment is updated, not duplicated."""
    monkeypatch.setenv("EC2_PUBLIC_IP", "1.2.3.4")

    mock_github_client.find_bot_comment.return_value = 987654321

    result = create_environment(
        k8s=mock_k8s_client,
        namespace="pr-456",
        config_path=test_config_file,
        template_dir=template_dir,
        github=mock_github_client,
    )

    assert result is True

    mock_github_client.find_bot_comment.assert_called_once_with(456)
    mock_github_client.update_comment.assert_called_once()
    mock_github_client.post_comment.assert_not_called()

    call_args = mock_github_client.update_comment.call_args
    assert call_args[0][0] == 456
    assert call_args[0][1] == 987654321
    message = call_args[0][2]
    assert "1.2.3.4" in message


def test_create_environment_no_github_comment_without_client(
    mock_k8s_client, test_config_file, template_dir
):
    """Test that no comment is posted when GitHub client is None."""
    result = create_environment(
        k8s=mock_k8s_client,
        namespace="pr-999",
        config_path=test_config_file,
        template_dir=template_dir,
        github=None,
    )

    assert result is True


def test_create_environment_no_github_comment_without_ingress(
    mock_k8s_client, mock_github_client, tmp_path, template_dir
):
    """Test that no comment is posted when no ingress is created."""
    config = tmp_path / "no-ingress-config.yaml"
    config.write_text(
        """
services:
  - name: database
    image: postgres:latest
    port: 5432
"""
    )

    result = create_environment(
        k8s=mock_k8s_client,
        namespace="pr-999",
        config_path=str(config),
        template_dir=template_dir,
        github=mock_github_client,
    )

    assert result is True

    mock_github_client.post_comment.assert_not_called()
    mock_github_client.update_comment.assert_not_called()


def test_create_environment_missing_config(mock_k8s_client, template_dir):
    """Test environment creation with missing config file."""
    result = create_environment(
        k8s=mock_k8s_client,
        namespace="pr-999",
        config_path="nonexistent.yaml",
        template_dir=template_dir,
        github=None,
    )

    assert result is False

    mock_k8s_client.create_namespace.assert_not_called()


def test_create_environment_namespace_failure(mock_k8s_client, test_config_file, template_dir):
    """Test environment creation when namespace creation fails."""
    mock_k8s_client.create_namespace.side_effect = KubernetesError("Failed to create namespace")

    result = create_environment(
        k8s=mock_k8s_client,
        namespace="pr-999",
        config_path=test_config_file,
        template_dir=template_dir,
        github=None,
    )

    assert result is False

    mock_k8s_client.create_deployment.assert_not_called()


def test_create_environment_deployment_failure(mock_k8s_client, test_config_file, template_dir):
    """Test environment creation when deployment fails."""

    mock_k8s_client.create_deployment.side_effect = KubernetesError("Failed to create deployment")

    result = create_environment(
        k8s=mock_k8s_client,
        namespace="pr-999",
        config_path=test_config_file,
        template_dir=template_dir,
        github=None,
    )

    assert result is False


def test_create_environment_service_failure(mock_k8s_client, test_config_file, template_dir):
    """Test environment creation when service creation fails."""
    mock_k8s_client.create_service.side_effect = KubernetesError("Failed to create service")

    result = create_environment(
        k8s=mock_k8s_client,
        namespace="pr-999",
        config_path=test_config_file,
        template_dir=template_dir,
        github=None,
    )

    assert result is False


def test_create_environment_middleware_failure(mock_k8s_client, test_config_file, template_dir):
    """Test environment creation when middleware creation fails."""
    mock_k8s_client.create_middleware.side_effect = KubernetesError("Failed to create middleware")

    result = create_environment(
        k8s=mock_k8s_client,
        namespace="pr-999",
        config_path=test_config_file,
        template_dir=template_dir,
        github=None,
    )

    assert result is False


def test_create_environment_ingress_failure(mock_k8s_client, test_config_file, template_dir):
    """Test environment creation when ingress creation fails."""
    mock_k8s_client.create_ingress.side_effect = KubernetesError("Failed to create ingress")

    result = create_environment(
        k8s=mock_k8s_client,
        namespace="pr-999",
        config_path=test_config_file,
        template_dir=template_dir,
        github=None,
    )

    assert result is False


def test_create_environment_github_exception_handled(
    mock_k8s_client, mock_github_client, test_config_file, template_dir, monkeypatch
):
    """Test that GitHub exceptions don't break environment creation."""
    monkeypatch.setenv("EC2_PUBLIC_IP", "1.2.3.4")

    mock_github_client.post_comment.side_effect = GitHubError("GitHub API error")

    result = create_environment(
        k8s=mock_k8s_client,
        namespace="pr-999",
        config_path=test_config_file,
        template_dir=template_dir,
        github=mock_github_client,
    )

    assert result is True


def test_create_environment_github_comment_includes_all_ingress_services(
    mock_k8s_client, mock_github_client, test_config_file, template_dir, monkeypatch
):
    """Test that GitHub comment includes all ingress-enabled services."""
    monkeypatch.setenv("EC2_PUBLIC_IP", "10.20.30.40")

    result = create_environment(
        k8s=mock_k8s_client,
        namespace="pr-555",
        config_path=test_config_file,
        template_dir=template_dir,
        github=mock_github_client,
    )

    assert result is True

    call_args = mock_github_client.post_comment.call_args
    message = call_args[0][1]

    assert "Frontend:" in message
    assert "http://10.20.30.40/pr-555/" in message
    assert "Backend:" in message
    assert "http://10.20.30.40/pr-555/api" in message

    assert "Database:" not in message


# ============================================================================
# DELETE ENVIRONMENT TESTS
# ============================================================================


def test_delete_environment_success(mock_k8s_client):
    """Test successful environment deletion."""
    result = delete_environment(k8s=mock_k8s_client, namespace="pr-999")

    assert result is True
    mock_k8s_client.delete_namespace.assert_called_once_with("pr-999")


def test_delete_environment_failure(mock_k8s_client):
    """Test environment deletion failure."""
    mock_k8s_client.delete_namespace.side_effect = KubernetesError("Failed to delete namespace")

    result = delete_environment(k8s=mock_k8s_client, namespace="pr-999")

    assert result is False

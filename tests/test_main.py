"""
Tests for main.py orchestration functions
"""

import sys
from unittest.mock import Mock, patch

import pytest

from automation.constants import EC2_PUBLIC_IP, GITHUB_REPO, GITHUB_RUN_ID, GITHUB_TOKEN, LOG_FILE
from automation.exceptions import GitHubError, KubernetesError
from automation.main import create_environment, delete_environment, main


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
    monkeypatch.setenv(EC2_PUBLIC_IP, "1.2.3.4")

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
    monkeypatch.setenv(EC2_PUBLIC_IP, "1.2.3.4")

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
    monkeypatch.setenv(EC2_PUBLIC_IP, "1.2.3.4")

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
    monkeypatch.setenv(EC2_PUBLIC_IP, "10.20.30.40")

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


# ============================================================================
# MAIN CLI TESTS
# ============================================================================


@patch("automation.main.delete_environment")
@patch("automation.main.GithubClient")
@patch("automation.main.KubernetesClient")
@patch("automation.main.setup_logging")
@patch("automation.main.set_operation_id")
def test_main_delete_action_success(
    mock_set_op_id, mock_setup_logging, mock_k8s_cls, mock_gh_cls, mock_delete_env, monkeypatch
):
    """Test main() with delete action executes successfully."""
    monkeypatch.setattr(sys, "argv", ["main.py", "delete", "123"])

    mock_delete_env.return_value = True
    mock_k8s_instance = Mock()
    mock_k8s_cls.return_value = mock_k8s_instance

    main()

    mock_delete_env.assert_called_once_with(mock_k8s_instance, "pr-123")
    mock_set_op_id.assert_called_once()


@patch("automation.main.create_environment")
@patch("automation.main.GithubClient")
@patch("automation.main.KubernetesClient")
@patch("automation.main.setup_logging")
@patch("automation.main.set_operation_id")
def test_main_create_action_success(
    mock_set_op_id, mock_setup_logging, mock_k8s_cls, mock_gh_cls, mock_create_env, monkeypatch
):
    """Test main() with create action executes successfully."""
    monkeypatch.setattr(sys, "argv", ["main.py", "create", "456"])

    mock_create_env.return_value = True
    mock_k8s_instance = Mock()
    mock_k8s_cls.return_value = mock_k8s_instance

    main()

    assert mock_create_env.call_count == 1
    call_args = mock_create_env.call_args
    assert call_args[0][0] == mock_k8s_instance  # k8s client
    assert call_args[0][1] == "pr-456"  # namespace


@patch("automation.main.create_environment")
@patch("automation.main.GithubClient")
@patch("automation.main.KubernetesClient")
@patch("automation.main.setup_logging")
@patch("automation.main.set_operation_id")
def test_main_with_skip_github_flag(
    mock_set_op_id, mock_setup_logging, mock_k8s_cls, mock_gh_cls, mock_create_env, monkeypatch
):
    """Test --skip-github flag prevents GitHub client initialization."""
    monkeypatch.setattr(sys, "argv", ["main.py", "create", "789", "--skip-github"])
    monkeypatch.setenv(GITHUB_TOKEN, "fake-token")
    monkeypatch.setenv(GITHUB_REPO, "owner/repo")

    mock_create_env.return_value = True
    mock_k8s_cls.return_value = Mock()

    main()

    # GitHub client should not be initialized
    mock_gh_cls.assert_not_called()

    # create_environment should be called with github=None
    call_args = mock_create_env.call_args
    assert call_args[0][4] is None  # github parameter


@patch("automation.main.create_environment")
@patch("automation.main.GithubClient")
@patch("automation.main.KubernetesClient")
@patch("automation.main.setup_logging")
@patch("automation.main.set_operation_id")
def test_main_github_client_initialized_with_credentials(
    mock_set_op_id, mock_setup_logging, mock_k8s_cls, mock_gh_cls, mock_create_env, monkeypatch
):
    """Test GitHub client is initialized when credentials are provided."""
    monkeypatch.setattr(sys, "argv", ["main.py", "create", "999"])
    monkeypatch.setenv(GITHUB_TOKEN, "test-token")
    monkeypatch.setenv(GITHUB_REPO, "test-owner/test-repo")

    mock_create_env.return_value = True
    mock_k8s_cls.return_value = Mock()
    mock_gh_instance = Mock()
    mock_gh_cls.return_value = mock_gh_instance

    main()

    mock_gh_cls.assert_called_once_with(token="test-token", repo_name="test-owner/test-repo")

    # create_environment should be called with the GitHub client
    call_args = mock_create_env.call_args
    assert call_args[0][4] == mock_gh_instance


@patch("automation.main.load_dotenv")
@patch("automation.main.create_environment")
@patch("automation.main.GithubClient")
@patch("automation.main.KubernetesClient")
@patch("automation.main.setup_logging")
@patch("automation.main.set_operation_id")
def test_main_github_client_not_initialized_without_token(
    mock_set_op_id,
    mock_setup_logging,
    mock_k8s_cls,
    mock_gh_cls,
    mock_create_env,
    mock_load_dotenv,
    monkeypatch,
):
    """Test GitHub client is not initialized when token is missing."""
    monkeypatch.setattr(sys, "argv", ["main.py", "create", "111"])
    monkeypatch.delenv(GITHUB_TOKEN, raising=False)
    monkeypatch.setenv(GITHUB_REPO, "owner/repo")

    mock_create_env.return_value = True
    mock_k8s_cls.return_value = Mock()

    main()

    mock_gh_cls.assert_not_called()

    call_args = mock_create_env.call_args
    assert call_args[0][4] is None


@patch("automation.main.load_dotenv")
@patch("automation.main.create_environment")
@patch("automation.main.GithubClient")
@patch("automation.main.KubernetesClient")
@patch("automation.main.setup_logging")
@patch("automation.main.set_operation_id")
def test_main_github_client_not_initialized_without_repo(
    mock_set_op_id,
    mock_setup_logging,
    mock_k8s_cls,
    mock_gh_cls,
    mock_create_env,
    mock_load_dotenv,
    monkeypatch,
):
    """Test GitHub client is not initialized when repo is missing."""
    monkeypatch.setattr(sys, "argv", ["main.py", "create", "222"])
    monkeypatch.setenv(GITHUB_TOKEN, "test-token")
    monkeypatch.delenv(GITHUB_REPO, raising=False)

    mock_create_env.return_value = True
    mock_k8s_cls.return_value = Mock()

    main()

    mock_gh_cls.assert_not_called()

    call_args = mock_create_env.call_args
    assert call_args[0][4] is None


@patch("automation.main.create_environment")
@patch("automation.main.GithubClient")
@patch("automation.main.KubernetesClient")
@patch("automation.main.setup_logging")
@patch("automation.main.set_operation_id")
def test_main_github_run_id_sets_operation_id(
    mock_set_op_id, mock_setup_logging, mock_k8s_cls, mock_gh_cls, mock_create_env, monkeypatch
):
    """Test GITHUB_RUN_ID environment variable is used for operation ID."""
    monkeypatch.setattr(sys, "argv", ["main.py", "create", "333"])
    monkeypatch.setenv(GITHUB_RUN_ID, "12345678")

    mock_create_env.return_value = True
    mock_k8s_cls.return_value = Mock()

    main()

    mock_set_op_id.assert_called_once_with("12345678")


@patch("automation.main.create_environment")
@patch("automation.main.GithubClient")
@patch("automation.main.KubernetesClient")
@patch("automation.main.setup_logging")
@patch("automation.main.set_operation_id")
def test_main_no_github_run_id_sets_random_operation_id(
    mock_set_op_id, mock_setup_logging, mock_k8s_cls, mock_gh_cls, mock_create_env, monkeypatch
):
    """Test operation ID is generated when GITHUB_RUN_ID is not set."""
    monkeypatch.setattr(sys, "argv", ["main.py", "create", "444"])
    monkeypatch.delenv(GITHUB_RUN_ID, raising=False)

    mock_create_env.return_value = True
    mock_k8s_cls.return_value = Mock()

    main()

    # Should be called without arguments
    mock_set_op_id.assert_called_once_with()


@patch("automation.main.delete_environment")
@patch("automation.main.GithubClient")
@patch("automation.main.KubernetesClient")
@patch("automation.main.setup_logging")
@patch("automation.main.set_operation_id")
def test_main_exits_on_operation_failure(
    mock_set_op_id, mock_setup_logging, mock_k8s_cls, mock_gh_cls, mock_delete_env, monkeypatch
):
    """Test main() exits with code 1 when operation fails."""
    monkeypatch.setattr(sys, "argv", ["main.py", "delete", "555"])

    mock_delete_env.return_value = False
    mock_k8s_cls.return_value = Mock()

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 1


@patch("automation.main.create_environment")
@patch("automation.main.GithubClient")
@patch("automation.main.KubernetesClient")
@patch("automation.main.setup_logging")
@patch("automation.main.set_operation_id")
def test_main_exits_on_kubernetes_client_failure(
    mock_set_op_id, mock_setup_logging, mock_k8s_cls, mock_gh_cls, mock_create_env, monkeypatch
):
    """Test main() exits with code 1 when Kubernetes client initialization fails."""
    monkeypatch.setattr(sys, "argv", ["main.py", "create", "666"])

    mock_k8s_cls.side_effect = Exception("K8s initialization failed")

    with pytest.raises(SystemExit) as exc_info:
        main()

    assert exc_info.value.code == 1
    mock_create_env.assert_not_called()


@patch("automation.main.create_environment")
@patch("automation.main.GithubClient")
@patch("automation.main.KubernetesClient")
@patch("automation.main.setup_logging")
@patch("automation.main.set_operation_id")
def test_main_custom_config_and_template_paths(
    mock_set_op_id, mock_setup_logging, mock_k8s_cls, mock_gh_cls, mock_create_env, monkeypatch
):
    """Test custom --config and --templates arguments are passed correctly."""
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "main.py",
            "create",
            "777",
            "--config",
            "/custom/config.yaml",
            "--templates",
            "/custom/templates",
        ],
    )

    mock_create_env.return_value = True
    mock_k8s_cls.return_value = Mock()

    main()

    call_args = mock_create_env.call_args
    assert call_args[0][2] == "/custom/config.yaml"  # config_path
    assert call_args[0][3] == "/custom/templates"  # template_dir


@patch("automation.main.create_environment")
@patch("automation.main.GithubClient")
@patch("automation.main.KubernetesClient")
@patch("automation.main.setup_logging")
@patch("automation.main.set_operation_id")
def test_main_log_level_from_argument(
    mock_set_op_id, mock_setup_logging, mock_k8s_cls, mock_gh_cls, mock_create_env, monkeypatch
):
    """Test --log-level argument configures logging correctly."""
    monkeypatch.setattr(sys, "argv", ["main.py", "create", "888", "--log-level", "DEBUG"])

    mock_create_env.return_value = True
    mock_k8s_cls.return_value = Mock()

    main()

    call_args = mock_setup_logging.call_args
    assert call_args[1]["level"] == "DEBUG"


@patch("automation.main.create_environment")
@patch("automation.main.GithubClient")
@patch("automation.main.KubernetesClient")
@patch("automation.main.setup_logging")
@patch("automation.main.set_operation_id")
def test_main_log_format_from_argument(
    mock_set_op_id, mock_setup_logging, mock_k8s_cls, mock_gh_cls, mock_create_env, monkeypatch
):
    """Test --log-format argument configures logging correctly."""
    monkeypatch.setattr(sys, "argv", ["main.py", "create", "900", "--log-format", "json"])

    mock_create_env.return_value = True
    mock_k8s_cls.return_value = Mock()

    main()

    call_args = mock_setup_logging.call_args
    assert call_args[1]["log_format"] == "json"


@patch("automation.main.create_environment")
@patch("automation.main.GithubClient")
@patch("automation.main.KubernetesClient")
@patch("automation.main.setup_logging")
@patch("automation.main.set_operation_id")
def test_main_log_file_from_environment_variable(
    mock_set_op_id, mock_setup_logging, mock_k8s_cls, mock_gh_cls, mock_create_env, monkeypatch
):
    """Test LOG_FILE environment variable sets log file path."""
    monkeypatch.setattr(sys, "argv", ["main.py", "create", "1001"])
    monkeypatch.setenv(LOG_FILE, "/custom/log/path.log")

    mock_create_env.return_value = True
    mock_k8s_cls.return_value = Mock()

    main()

    call_args = mock_setup_logging.call_args
    assert call_args[1]["log_file"] == "/custom/log/path.log"


@patch("automation.main.create_environment")
@patch("automation.main.GithubClient")
@patch("automation.main.KubernetesClient")
@patch("automation.main.setup_logging")
@patch("automation.main.set_operation_id")
def test_main_log_file_empty_string_disables_file_logging(
    mock_set_op_id, mock_setup_logging, mock_k8s_cls, mock_gh_cls, mock_create_env, monkeypatch
):
    """Test LOG_FILE empty string disables file logging."""
    monkeypatch.setattr(sys, "argv", ["main.py", "create", "1002"])
    monkeypatch.setenv(LOG_FILE, "")

    mock_create_env.return_value = True
    mock_k8s_cls.return_value = Mock()

    main()

    call_args = mock_setup_logging.call_args
    assert call_args[1]["log_file"] is None


@patch("automation.main.create_environment")
@patch("automation.main.GithubClient")
@patch("automation.main.KubernetesClient")
@patch("automation.main.setup_logging")
@patch("automation.main.set_operation_id")
def test_main_github_client_exception_handled_gracefully(
    mock_set_op_id, mock_setup_logging, mock_k8s_cls, mock_gh_cls, mock_create_env, monkeypatch
):
    """Test GitHub client initialization exceptions are handled gracefully."""
    monkeypatch.setattr(sys, "argv", ["main.py", "create", "1003"])
    monkeypatch.setenv(GITHUB_TOKEN, "test-token")
    monkeypatch.setenv(GITHUB_REPO, "owner/repo")

    mock_create_env.return_value = True
    mock_k8s_cls.return_value = Mock()
    mock_gh_cls.side_effect = Exception("GitHub API error")

    # Should not raise, should continue with github=None
    main()

    call_args = mock_create_env.call_args
    assert call_args[0][4] is None  # github should be None

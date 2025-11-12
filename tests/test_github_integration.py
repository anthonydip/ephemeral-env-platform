"""
Tests for github_integration.py

These tests mock the PyGithub library to avoid real API calls.
"""

from unittest.mock import Mock, patch

import pytest
from github import GithubException

from automation.constants import PREVIEW_READY_MARKER
from automation.exceptions import GitHubError
from automation.github_integration import GithubClient


@pytest.fixture
def mock_github_client(monkeypatch):
    """Create a GithubClient with mocked GitHub connection."""
    # Mock Auth.Token
    mock_auth = Mock()
    monkeypatch.setattr("automation.github_integration.Auth.Token", Mock(return_value=mock_auth))

    # Mock Github client
    mock_github = Mock()
    monkeypatch.setattr("automation.github_integration.Github", Mock(return_value=mock_github))

    # Mock the repo
    mock_repo = Mock()
    mock_repo.full_name = "test-owner/test-repo"
    mock_github.get_repo.return_value = mock_repo

    client = GithubClient(token="test-token", repo_name="test-owner/test-repo")
    client.repo = mock_repo

    return client


def test_post_comment_success(mock_github_client):
    """Test successfully posting a comment."""
    mock_pr = Mock()
    mock_comment = Mock()
    mock_comment.id = 123456789
    mock_pr.create_issue_comment.return_value = mock_comment
    mock_github_client.repo.get_pull.return_value = mock_pr

    mock_github_client.post_comment(42, "Test message")

    mock_github_client.repo.get_pull.assert_called_once_with(42)
    mock_pr.create_issue_comment.assert_called_once_with("Test message")


def test_post_comment_github_exception(mock_github_client):
    """Test posting comment with GitHub API error."""
    mock_pr = Mock()
    mock_pr.create_issue_comment.side_effect = GithubException(
        status=403, data={"message": "Forbidden"}, headers={}
    )
    mock_github_client.repo.get_pull.return_value = mock_pr

    with pytest.raises(GitHubError, match="Failed to post comment"):
        mock_github_client.post_comment(42, "Test message")


def test_post_comment_unexpected_exception(mock_github_client):
    """Test posting comment with unexpected error."""
    mock_pr = Mock()
    mock_pr.create_issue_comment.side_effect = ValueError("Unexpected error")
    mock_github_client.repo.get_pull.return_value = mock_pr

    with pytest.raises(GitHubError, match="Unexpected error posting"):
        mock_github_client.post_comment(42, "Test message")


def test_find_bot_comment_success(mock_github_client):
    """Test finding an existing bot comment."""
    mock_pr = Mock()

    comment1 = Mock()
    comment1.id = 111
    comment1.body = "Some other comment"

    comment2 = Mock()
    comment2.id = 222
    comment2.body = f"{PREVIEW_READY_MARKER}\n\nFrontend: http://..."

    comment3 = Mock()
    comment3.id = 333
    comment3.body = "Another comment"

    mock_pr.get_issue_comments.return_value = [comment1, comment2, comment3]
    mock_github_client.repo.get_pull.return_value = mock_pr

    result = mock_github_client.find_bot_comment(42)

    assert result == 222


def test_find_bot_comment_empty_pr(mock_github_client):
    """Test finding comment on PR with no comments."""
    mock_pr = Mock()
    mock_pr.get_issue_comments.return_value = []
    mock_github_client.repo.get_pull.return_value = mock_pr

    result = mock_github_client.find_bot_comment(42)

    assert result is None


def test_find_bot_comment_github_exception(mock_github_client):
    """Test finding comment with GitHub API error."""
    mock_github_client.repo.get_pull.side_effect = GithubException(
        status=404, data={"message": "Not Found"}, headers={}
    )

    with pytest.raises(GitHubError, match="Failed to search"):
        mock_github_client.find_bot_comment(42)


def test_find_bot_comment_unexpected_exception(mock_github_client):
    """Test finding comment with unexpected error."""
    mock_github_client.repo.get_pull.side_effect = ValueError("Unexpected error")

    with pytest.raises(GitHubError, match="Unexpected error finding"):
        mock_github_client.find_bot_comment(42)


def test_update_comment_success(mock_github_client):
    """Test successfully updating a comment."""
    mock_pr = Mock()
    mock_comment = Mock()
    mock_pr.get_issue_comment.return_value = mock_comment
    mock_github_client.repo.get_pull.return_value = mock_pr

    mock_github_client.update_comment(42, 123456789, "Updated message")

    mock_pr.get_issue_comment.assert_called_once_with(123456789)
    mock_comment.edit.assert_called_once_with("Updated message")


def test_update_comment_github_exception(mock_github_client):
    """Test updating comment with GitHub API error."""
    mock_pr = Mock()
    mock_pr.get_issue_comment.side_effect = GithubException(
        status=404, data={"message": "Not Found"}, headers={}
    )
    mock_github_client.repo.get_pull.return_value = mock_pr

    with pytest.raises(GitHubError, match="Failed to update"):
        mock_github_client.update_comment(42, 123456789, "Updated message")


def test_update_comment_unexpected_exception(mock_github_client):
    """Test updating comment with unexpected error."""
    mock_pr = Mock()
    mock_pr.get_issue_comment.side_effect = ValueError("Unexpected error")
    mock_github_client.repo.get_pull.return_value = mock_pr

    with pytest.raises(GitHubError, match="Unexpected error updating"):
        mock_github_client.update_comment(42, 123456789, "Updated message")


def test_initialization_failure():
    """Test GithubClient initialization with invalid credentials."""
    with patch("automation.github_integration.Github") as mock_github_class:
        mock_github_class.side_effect = GithubException(
            status=401, data={"message": "Bad credentials"}, headers={}
        )

        with pytest.raises(GithubException) as exc_info:
            GithubClient(token="bad-token", repo_name="test/repo")

        assert exc_info.value.status == 401

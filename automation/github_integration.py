"""
Github integration for ephemeral environment platform.

Posts Github comment to PR to display the preview environment URL for viewing.
"""

from __future__ import annotations

from github import Auth, Github

from automation.logger import get_logger

logger = get_logger(__name__)


class GithubClient:
    """
    Wrapper for GitHub API operations.
    """

    def __init__(self, token: str, repo_name: str):
        """
        Initialize GitHub client.

        Args:
            token: GitHub authentication token
            repo_name: Repository in format "owner/repo"
        """
        try:
            auth = Auth.Token(token)
            self.client = Github(auth=auth)
            self.repo = self.client.get_repo(repo_name)
            logger.info(f"GitHub client initialized for {repo_name} successfully")
        except Exception as e:
            logger.critical(f"Failed to initialize GitHub client: {e}")
            raise

"""
Github integration for ephemeral environment platform.

Posts Github comment to PR to display the preview environment URL for viewing.
"""

from __future__ import annotations

from github import Auth, Github, GithubException

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

    def post_comment(self, pr_number: int, message: str) -> bool:
        """
        Post a new comment to a PR.

        Args:
            pr_number: Pull request number
            message: Comment message content

        Returns:
            True if successful, False otherwise
        """
        try:
            pr = self.repo.get_pull(pr_number)
            comment = pr.create_issue_comment(message)
            logger.info(
                f"Posted comment {comment.id} to PR #{pr_number}",
                extra={"pr_number": pr_number, "comment_id": comment.id},
            )
            return True
        except GithubException as e:
            logger.error(
                f"Failed to post comment to PR #{pr_number}",
                extra={"pr_number": pr_number, "error": str(e)},
            )
            return False
        except Exception as e:
            logger.error(
                "Unexpected error posting comment", extra={"pr_number": pr_number, "error": str(e)}
            )
            return False

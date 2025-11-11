"""
Github integration for ephemeral environment platform.

Posts Github comment to PR to display the preview environment URL for viewing.
"""

from __future__ import annotations

from github import Auth, Github, GithubException

from automation.exceptions import GitHubError
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

    def post_comment(self, pr_number: int, message: str) -> None:
        """
        Post a new comment to a PR.

        Args:
            pr_number: Pull request number
            message: Comment message content

        Raises:
            GitHubError: If comment posting fails
        """
        try:
            pr = self.repo.get_pull(pr_number)
            comment = pr.create_issue_comment(message)
            logger.info(
                f"Posted comment {comment.id} to PR #{pr_number}",
                extra={"pr_number": pr_number, "comment_id": comment.id},
            )
        except GithubException as e:
            raise GitHubError(f"Failed to post comment to PR #{pr_number}: {e}") from e
        except Exception as e:
            raise GitHubError(f"Unexpected error posting comment to PR #{pr_number}: {e}") from e

    def find_bot_comment(self, pr_number: int) -> int | None:
        """
        Find existing comment from the bot on the PR.

        Args:
            pr_number: Pull request number

        Returns:
            Comment ID if found, None if not found

        Raises:
            GitHubError: If search fails
        """
        try:
            pr = self.repo.get_pull(pr_number)
            comments = pr.get_issue_comments()

            # Search for bot's comment
            for comment in comments:
                if "🚀 **Preview Environment Ready!**" in comment.body:
                    logger.info(
                        f"Found existing bot comment {comment.id} on PR #{pr_number}",
                        extra={"pr_number": pr_number, "comment_id": comment.id},
                    )
                    return comment.id

            logger.info(f"No existing bot comment found on PR #{pr_number}")
            return None
        except GithubException as e:
            raise GitHubError(f"Failed to search for bot comment on PR #{pr_number}: {e}") from e
        except Exception as e:
            raise GitHubError(f"Unexpected error finding comment on PR #{pr_number}: {e}") from e

    def update_comment(self, pr_number: int, comment_id: int, message: str) -> None:
        """
        Update an existing comment.

        Args:
            pr_number: Pull request number
            comment_id: ID of the comment to update
            message: New message content

        Raises:
            GitHubError: If update fails
        """
        try:
            pr = self.repo.get_pull(pr_number)
            comment = pr.get_issue_comment(comment_id)
            comment.edit(message)
            logger.info(
                f"Updated comment {comment_id} on PR #{pr_number}",
                extra={"comment_id": comment_id, "pr_number": pr_number},
            )
        except GithubException as e:
            raise GitHubError(
                f"Failed to update comment {comment_id} on PR #{pr_number}: {e}"
            ) from e
        except Exception as e:
            raise GitHubError(
                f"Unexpected error updating comment {comment_id} on PR #{pr_number}: {e}"
            ) from e

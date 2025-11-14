"""
Main automation script for ephemeral environments.

Creates and destroys Kubernetes namespaces for PR preview environments.
"""

from __future__ import annotations

import argparse
import os
import sys
import time

from dotenv import load_dotenv

from automation.config_parser import load_config
from automation.constants import (
    DEFAULT_CONFIG_PATH,
    DEFAULT_LOG_FILE,
    DEFAULT_LOG_FORMAT,
    DEFAULT_LOG_LEVEL,
    DEFAULT_TEMPLATE_DIR,
    EC2_PUBLIC_IP,
    GITHUB_REPO,
    GITHUB_RUN_ID,
    GITHUB_TOKEN,
    LOG_FILE,
    LOG_LEVEL,
    NAMESPACE_PREFIX,
    PORT_FORWARD_OFFSET,
    PREVIEW_READY_MARKER,
    STRIPPREFIX_MIDDLEWARE,
)
from automation.context import set_operation_id
from automation.exceptions import (
    ConfigError,
    GitHubError,
    KubernetesError,
    TemplateError,
    ValidationError,
)
from automation.github_integration import GithubClient
from automation.k8s_client import KubernetesClient
from automation.logger import get_logger, setup_logging


def main() -> None:
    """
    CLI entry point for ephemeral environment management.

    Parses command line arguments and delegates to appropriate handler.
    Exits with code 1 on invalid input.
    """
    load_dotenv()

    parser = argparse.ArgumentParser(description="Manage ephemeral preview environments")
    parser.add_argument("action", choices=["create", "delete"], help="Action to perform")
    parser.add_argument("pr_number", help="Pull request number")
    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG_PATH,
        help=f"Path to config file (default: {DEFAULT_CONFIG_PATH})",
    )
    parser.add_argument(
        "--templates",
        default=DEFAULT_TEMPLATE_DIR,
        help=f"Path to templates directory (default: {DEFAULT_TEMPLATE_DIR})",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default=os.getenv(LOG_LEVEL, DEFAULT_LOG_LEVEL),
        help=f"Set logging level (default: {DEFAULT_LOG_LEVEL})",
    )
    parser.add_argument(
        "--skip-github",
        action="store_true",
        help="Skip GitHub integration (don't post PR comments)",
    )
    parser.add_argument(
        "--log-format",
        choices=["text", "structured", "json"],
        default=DEFAULT_LOG_FORMAT,
        help=f"Log output format (default: {DEFAULT_LOG_FORMAT})",
    )

    args = parser.parse_args()

    # Determine log file path
    log_file_env = os.getenv(LOG_FILE)
    if log_file_env == "":
        log_file = None
    elif log_file_env is None:
        log_file = DEFAULT_LOG_FILE
    else:
        log_file = log_file_env

    # Configure logging once at startup
    setup_logging(level=args.log_level, log_file=log_file, log_format=args.log_format)

    # Use GitHub Actions run ID if provided
    github_run_id = os.getenv(GITHUB_RUN_ID)
    set_operation_id(github_run_id) if github_run_id else set_operation_id()

    logger = get_logger(__name__)

    namespace = f"{NAMESPACE_PREFIX}{args.pr_number}"

    logger.info(
        f"Starting {args.action} operation",
        extra={"action": args.action, "pr_number": args.pr_number, "namespace": namespace},
    )

    # Initialize Kubernetes client
    try:
        k8s = KubernetesClient()
    except Exception:
        logger.critical("Kubernetes client initialization failed", extra={"action": args.action})
        sys.exit(1)

    # Initialize GitHub client (optional)
    github_token = os.getenv(GITHUB_TOKEN)
    github_repo = os.getenv(GITHUB_REPO)

    if args.skip_github:
        logger.info(
            "GitHub integration disabled, skipped via --skip-github flag",
            extra={"skip_github": True},
        )
        github = None
    elif github_token and github_repo:
        try:
            github = GithubClient(token=github_token, repo_name=github_repo)
        except Exception as e:
            logger.warning(f"GitHub integration disabled: {e}", extra={"error": str(e)})
            github = None
    else:
        logger.info(
            f"GitHub integration disabled, missing {GITHUB_TOKEN} or {GITHUB_REPO}",
            extra={"has_token": bool(github_token), "has_repo": bool(github_repo)},
        )
        github = None

    operation_start = time.perf_counter()

    if args.action == "create":
        success = create_environment(k8s, namespace, args.config, args.templates, github)
    elif args.action == "delete":
        success = delete_environment(k8s, namespace)

    duration = time.perf_counter() - operation_start

    if not success:
        logger.error(
            f"Operation {args.action} failed",
            extra={"namespace": namespace, "duration_seconds": round(duration, 3)},
        )
        sys.exit(1)

    logger.info(
        f"Operation {args.action} completed successfully",
        extra={
            "action": args.action,
            "namespace": namespace,
            "duration_seconds": round(duration, 3),
        },
    )


def create_environment(
    k8s: KubernetesClient,
    namespace: str,
    config_path: str,
    template_dir: str,
    github: GithubClient | None = None,
) -> bool:
    """
    Create a new ephemeral environment.

    Args:
        k8s: KubernetesClient instance
        namespace: Namespace name (e.g., 'pr-123')
        config_path: Path to configuration file
        template_dir: Path to templates directory
        github: Optional GithubClient instance for PR comments

    Returns:
        True if successful, False otherwise
    """
    logger = get_logger(__name__)

    start_time = time.perf_counter()

    logger.info(f"Creating environment: {namespace}", extra={"namespace": namespace})

    try:
        # Load YAML configuration file
        config = load_config(config_path)

        # Create namespace
        k8s.create_namespace(namespace)

        # Track deployment times
        deployment_times = []

        # Create services and deployments
        for service in config["services"]:
            service_start = time.perf_counter()

            k8s.create_deployment(
                name=service["name"],
                namespace=namespace,
                image=service["image"],
                port=service["port"],
                template_dir=template_dir,
                env_vars=service.get("env"),
            )

            k8s.create_service(
                name=service["name"],
                namespace=namespace,
                port=service["port"],
                target_port=service["port"],
                template_dir=template_dir,
            )

            service_duration = time.perf_counter() - service_start
            deployment_times.append(service_duration)

            logger.debug(
                f"Deployed service: {service['name']}",
                extra={
                    "service": service["name"],
                    "namespace": namespace,
                    "duration_seconds": round(service_duration, 3),
                },
            )

        # Create middleware for path stripping
        k8s.create_middleware(
            name=STRIPPREFIX_MIDDLEWARE,
            namespace=namespace,
            prefixes=[f"/{namespace}"],
            template_dir=template_dir,
        )

        # Create ingress for each service that has ingress.enabled = True
        ingress_created = False
        for service in config["services"]:
            if service.get("ingress", {}).get("enabled", False):
                service_path = service["ingress"].get("path", "/")
                full_path = f"/{namespace}{service_path}"

                k8s.create_ingress(
                    name=f"{namespace}-{service['name']}-ingress",
                    namespace=namespace,
                    path=full_path,
                    service_name=service["name"],
                    service_port=service["port"],
                    middleware_name=STRIPPREFIX_MIDDLEWARE,
                    template_dir=template_dir,
                )

                ingress_created = True
                logger.info(
                    f"Created ingress for {service['name']} at {full_path}",
                    extra={"namespace": namespace, "service": service["name"], "path": full_path},
                )

        ec2_ip = os.getenv(EC2_PUBLIC_IP, "<EC2-IP>")

        if ingress_created:
            logger.info(
                f"Preview environment accessible at: http://{ec2_ip}/{namespace}/",
                extra={"namespace": namespace, "url": f"http://{ec2_ip}/{namespace}/"},
            )
        else:
            logger.info(
                "No ingress configured - environment only accessible via port-forward",
                extra={"namespace": namespace, "ingress_created": False},
            )

        logger.info(
            "Access services directly with kubectl port-forward:", extra={"namespace": namespace}
        )
        for service in config["services"]:
            local_port = service["port"] + PORT_FORWARD_OFFSET
            logger.info(
                f"  kubectl port-forward -n {namespace} svc/{service['name']} {local_port}:{service['port']}",
                extra={
                    "namespace": namespace,
                    "service": service["name"],
                    "local_port": local_port,
                    "service_port": service["port"],
                },
            )

        # Post/update GitHub comment if integration is enabled
        if github and ingress_created:
            try:
                pr_number = int(namespace.replace(NAMESPACE_PREFIX, ""))

                # Build comment message with links to all ingress-enabled services
                service_links = []
                for service in config["services"]:
                    if service.get("ingress", {}).get("enabled", False):
                        service_path = service["ingress"].get("path", "/")
                        service_url = f"http://{ec2_ip}/{namespace}{service_path}"
                        service_links.append(f"**{service['name'].title()}:** {service_url}")

                links_text = "\n".join(service_links)

                message = f"{PREVIEW_READY_MARKER}\n\n{links_text}\n\nThe environment will be automatically deleted when this PR is closed."

                # Check if comment already exists
                existing_comment_id = github.find_bot_comment(pr_number)

                if existing_comment_id:
                    github.update_comment(pr_number, existing_comment_id, message)
                else:
                    github.post_comment(pr_number, message)

            except GitHubError as e:
                # GitHub integration is optional
                logger.warning(
                    f"Failed to post GitHub comment: {e}",
                    extra={"pr_number": pr_number, "error": str(e)},
                )

        total_duration = time.perf_counter() - start_time

        logger.info(
            "Environment created successfully",
            extra={
                "namespace": namespace,
                "service_count": len(config["services"]),
                "total_duration_seconds": round(total_duration, 3),
                "avg_service_duration_seconds": (
                    round(sum(deployment_times) / len(deployment_times), 3)
                    if deployment_times
                    else 0
                ),
            },
        )

        return True

    except ConfigError as e:
        logger.error(str(e), extra={"namespace": namespace, "error_type": "ConfigError"})
        return False
    except ValidationError as e:
        logger.error(str(e), extra={"namespace": namespace, "error_type": "ValidationError"})
        return False
    except TemplateError as e:
        logger.error(str(e), extra={"namespace": namespace, "error_type": "TemplateError"})
        return False
    except KubernetesError as e:
        logger.error(str(e), extra={"namespace": namespace, "error_type": "KubernetesError"})
        return False
    except Exception as e:
        logger.error(str(e), extra={"namespace": namespace, "error_type": type(e).__name__})
        return False


def delete_environment(k8s: KubernetesClient, namespace: str) -> bool:
    """
    Delete an ephemeral environment and all its resources.

    Args:
        k8s: KubernetesClient instance
        namespace: Namespace name to delete

    Returns:
        True if successful, False otherwise
    """
    logger = get_logger(__name__)

    logger.info(f"Deleting environment: {namespace}", extra={"namespace": namespace})

    try:
        k8s.delete_namespace(namespace)

        logger.info(
            f"Environment successfully deleted: {namespace} (resources may take a few seconds to terminate)",
            extra={"namespace": namespace},
        )

        return True

    except ValidationError as e:
        logger.error(str(e), extra={"namespace": namespace, "error_type": "ValidationError"})
        return False
    except KubernetesError as e:
        logger.error(str(e), extra={"namespace": namespace, "error_type": "KubernetesError"})
        return False
    except Exception as e:
        logger.error(str(e), extra={"namespace": namespace, "error_type": type(e).__name__})
        return False


if __name__ == "__main__":
    main()

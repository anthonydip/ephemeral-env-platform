"""
Main automation script for ephemeral environments.

Creates and destroys Kubernetes namespaces for PR preview environments.
"""

from __future__ import annotations

import argparse
import os
import sys

from dotenv import load_dotenv

from automation.config_parser import load_config
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
        default=".ephemeral-config.yaml",
        help="Path to config file (default: .ephemeral-config.yaml)",
    )
    parser.add_argument(
        "--templates",
        default="automation/templates/",
        help="Path to templates directory (default: automation/templates/)",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default=os.getenv("LOG_LEVEL", "INFO"),
        help="Set logging level (default: INFO)",
    )

    args = parser.parse_args()

    # Determine log file path
    log_file_env = os.getenv("LOG_FILE")
    if log_file_env == "":
        log_file = None
    elif log_file_env is None:
        log_file = "logs/ephemeral-env.log"
    else:
        log_file = log_file_env

    # Configure logging once at startup
    setup_logging(level=args.log_level, log_file=log_file)

    logger = get_logger(__name__)

    namespace = f"pr-{args.pr_number}"

    logger.info(
        f"Starting {args.action} operation",
        extra={"action": args.action, "pr_number": args.pr_number, "namespace": namespace},
    )

    # Initialize Kubernetes client
    try:
        k8s = KubernetesClient()
    except Exception:
        logger.critical("Kubernetes client initialization failed")
        sys.exit(1)

    # Initialize GitHub client (optional)
    github_token = os.getenv("GITHUB_TOKEN")
    github_repo = os.getenv("GITHUB_REPO")

    if github_token and github_repo:
        try:
            github = GithubClient(token=github_token, repo_name=github_repo)
        except Exception as e:
            logger.warning(f"GitHub integration disabled: {e}")
            github = None
    else:
        logger.info("GitHub integration disabled - missing GITHUB_TOKEN or GITHUB_REPO")
        github = None

    if args.action == "create":
        success = create_environment(k8s, namespace, args.config, args.templates, github)
    elif args.action == "delete":
        success = delete_environment(k8s, namespace)

    if not success:
        logger.error(f"Operation {args.action} failed", extra={"namespace": namespace})
        sys.exit(1)

    logger.info(f"Operation {args.action} completed successfully")


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
    """
    logger = get_logger(__name__)

    logger.info(f"Creating environment: {namespace}", extra={"namespace": namespace})

    # Load YAML configuration file
    config = load_config(config_path)
    if not config:
        return False

    # Create namespace
    if not k8s.create_namespace(namespace):
        return False

    # Create services and deployments
    failed_services = []
    for service in config["services"]:
        deployment_success = k8s.create_deployment(
            name=service["name"],
            namespace=namespace,
            image=service["image"],
            port=service["port"],
            template_dir=template_dir,
            env_vars=service.get("env"),
        )

        service_success = k8s.create_service(
            name=service["name"],
            namespace=namespace,
            port=service["port"],
            target_port=service["port"],
            template_dir=template_dir,
        )

        if not (deployment_success and service_success):
            failed_services.append(service["name"])

    if failed_services:
        logger.error(
            "Some services failed to deploy",
            extra={"namespace": namespace, "failed_services": failed_services},
        )
        return False

    # Create middleware for path stripping
    middleware_success = k8s.create_middleware(
        name="stripprefix",
        namespace=namespace,
        prefixes=[f"/{namespace}"],
        template_dir=template_dir,
    )

    if not middleware_success:
        logger.error("Failed to create middleware", extra={"namespace": namespace})
        return False

    # Create ingress for each service that has ingress.enabled = True
    ingress_created = False
    for service in config["services"]:
        if service.get("ingress", {}).get("enabled", False):
            service_path = service["ingress"].get("path", "/")
            full_path = f"/{namespace}{service_path}"

            ingress_success = k8s.create_ingress(
                name=f"{namespace}-{service['name']}-ingress",
                namespace=namespace,
                path=full_path,
                service_name=service["name"],
                service_port=service["port"],
                middleware_name="stripprefix",
                template_dir=template_dir,
            )

            if not ingress_success:
                logger.error(
                    f"Failed to create ingress for {service['name']}",
                    extra={"namespace": namespace, "service": service["name"]},
                )
                return False

            ingress_created = True
            logger.info(
                f"Created ingress for {service['name']} at {full_path}",
                extra={"namespace": namespace, "service": service["name"], "path": full_path},
            )

    if ingress_created:
        logger.info(f"Preview environment accessible at: http://<EC2-IP>/{namespace}/")
    else:
        logger.info("No ingress configured - environment only accessible via port-forward")

    logger.info("Access services directly with kubectl port-forward:")
    for service in config["services"]:
        local_port = service["port"] + 1000
        logger.info(
            f"  kubectl port-forward -n {namespace} svc/{service['name']} {local_port}:{service['port']}"
        )

    return True


def delete_environment(k8s: KubernetesClient, namespace: str) -> bool:
    """
    Delete an ephemeral environment and all its resources.

    Args:
        k8s: KubernetesClient instance
        namespace: Namespace name to delete
    """
    logger = get_logger(__name__)

    logger.info(f"Deleting environment: {namespace}", extra={"namespace": namespace})

    if not k8s.delete_namespace(namespace):
        return False

    logger.info(
        f"Environment successfully deleted: {namespace} (resources may take a few seconds to terminate)",
        extra={"namespace": namespace},
    )

    return True


if __name__ == "__main__":
    main()

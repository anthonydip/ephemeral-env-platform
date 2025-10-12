"""
Main automation script for ephemeral environments.

Creates and destroys Kubernetes namespaces for PR preview environments.
"""

import argparse

from automation.config_parser import load_config
from automation.k8s_client import KubernetesClient


def main() -> None:
    """
    CLI entry point for ephemeral environment management.

    Parses command line arguments and delegates to appropriate handler.
    Exits with code 1 on invalid input.
    """
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

    args = parser.parse_args()

    namespace = f"pr-{args.pr_number}"
    k8s = KubernetesClient()

    if args.action == "create":
        create_environment(k8s, namespace, args.config, args.templates)
    elif args.action == "delete":
        delete_environment(k8s, namespace)


def create_environment(
    k8s: KubernetesClient, namespace: str, config_path: str, template_dir: str
) -> None:
    """
    Create a new ephemeral environment.

    Args:
        k8s: KubernetesClient instance
        namespace: Namespace name (e.g., 'pr-123')
        config_path: Path to configuration file
        template_dir: Path to templates directory
    """
    print(f"Creating environment: {namespace}")

    # Load YAML configuration file
    config = load_config(config_path)
    if not config:
        return

    # Create namespace
    if not k8s.create_namespace(namespace):
        return

    # Create services and deployments
    for service in config["services"]:
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

    print("\nEnvironment created!")
    for service in config["services"]:
        local_port = service["port"] + 1000
        print(
            f"    kubectl port-forward -n {namespace} svc/{service['name']} {local_port}:{service['port']}"
        )


def delete_environment(k8s: KubernetesClient, namespace: str) -> None:
    """
    Delete an ephemeral environment and all its resources.

    Args:
        k8s: KubernetesClient instance
        namespace: Namespace name to delete
    """
    print(f"Deleting environment: {namespace}")

    if not k8s.delete_namespace(namespace):
        return

    print("\nEnvironment deleted! (May take a few seconds to fully terminate)")


if __name__ == "__main__":
    main()

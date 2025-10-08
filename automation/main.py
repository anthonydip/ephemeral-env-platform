"""
Main automation script for ephemeral environments.

Creates and destroys Kubernetes namespaces for PR preview environments.
Run with: python main.py <create|delete> <pr-number>
"""
import sys
from k8s_client import KubernetesClient
from config_parser import load_config

def main():
    """
    CLI entry point for ephemeral environment management.

    Parsese command line arguments and delegates to appropriate handler.
    Exits with code 1 on invalid input.
    """
    if len(sys.argv) < 3:
        print("Usage: python main.py <create|delete> <pr-number>")
        sys.exit(1)

    action = sys.argv[1]
    pr_number = sys.argv[2]
    namespace = f"pr-{pr_number}"

    k8s = KubernetesClient()

    match action:
        case "create":
            create_environment(k8s, namespace)
        case "delete":
            delete_environment(k8s, namespace)
        case _:
            print(f"Unknown action: {action}")
            sys.exit(1)

def create_environment(k8s, namespace):
    """
    Create a new ephemeral environment.

    Args:
        k8s: KubernetesClient instance
        namespace: Namespace name (e.g., 'pr-123')
    """
    print(f"Creating environment: {namespace}")

    # Load YAML configuration file
    config = load_config("examples/.ephemeral-config.yml")
    if not config:
        return

    # Create namespace
    if not k8s.create_namespace(namespace):
        return

    # Create services and deployments
    for service in config['services']:
        k8s.create_deployment(
            name=service['name'],
            namespace=namespace,
            image=service['image'],
            port=service['port']
        )

        k8s.create_service(
            name=service['name'],
            namespace=namespace,
            port=service['port'],
            target_port=service['port']
        )

    print(f"\nEnvironment created!")
    for service in config['services']:
        local_port = service['port'] + 1000
        print(f"    kubectl port-forward -n {namespace} svc/{service['name']} {local_port}:{service['port']}")

def delete_environment(k8s, namespace):
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

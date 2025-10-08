"""
Main automation script for ephemeral environments.

Creates and destroys Kubernetes namespaces for PR preview environments.
Run with: python main.py <create|delete> <pr-number>
"""
import sys
from k8s_client import KubernetesClient

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

    if not k8s.create_namespace(namespace):
        return

    # Frontend deployment
    k8s.create_deployment(
        name="frontend",
        namespace=namespace,
        image="nginx:latest",
        port=80
    )

    # Backend deployment
    k8s.create_deployment(
        name="backend",
        namespace=namespace,
        image="node:alpine",
        port=3000
    )

    # Database deployment
    k8s.create_deployment(
        name="database",
        namespace=namespace,
        image="postgres:15",
        port=5432
    )

    k8s.create_service(
        name="frontend",
        namespace=namespace,
        port=80,
        target_port=80
    )

    k8s.create_service(
        name="backend",
        namespace=namespace,
        port=3000,
        target_port=3000
    )

    k8s.create_service(
        name="database",
        namespace=namespace,
        port=5432,
        target_port=5432
    )

    print(f"\nEnvironment created!")
    print(f"Access with frontend: kubectl port-forward -n {namespace} svc/frontend 8080:80")
    print(f"Access with backend: kubectl port-forward -n {namespace} svc/backend 3001:3000")
    print(f"Access with database: kubectl port-forward -n {namespace} svc/database 5433:5432")

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

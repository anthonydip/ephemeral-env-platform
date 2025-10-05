"""
Kubernetes client wrapper for namespace management.
"""
import re
from kubernetes import client, config
from kubernetes.client.rest import ApiException

class KubernetesClient:
    """
    Wrapper for Kubernetes API operations.
    """

    def __init__(self):
        """
        Initialize Kubernetes client.
        """
        # Load kubeconfig from default location (~/.kube/config)
        config.load_kube_config()
        self.v1 = client.CoreV1Api()

    @staticmethod
    def validate_namespace_name(name):
        """
        Validate namespace name according to Kubernetes rules.

        Args:
            name: Namespace name to validate

        Returns:
            tuple: (is_valid: bool, error_message: str or None)
        """
        if not name:
            return False, "Namespace name cannot be empty"

        if len(name) > 63:
            return False, f"Namespace name too long (max 63 chars, got {len(name)})"

        # Lowercase alphanumeric + hyphens, start/end with alphanumeric
        pattern = r'^[a-z0-9]([-a-z0-9]*[a-z0-9])?$'
        if not re.match(pattern, name):
            return False, (
                "Invalid namespace name. Must be lowercase letters, numbers, "
                "and hyphens only. Must start and end with alphanumeric character."
            )

        return True, None

    def create_namespace(self, name):
        """
        Create a namespace.

        Args:
            name: Name of the namespace to create

        Returns:
            True if successful, False otherwise
        """
        is_valid, error_msg = self.validate_namespace_name(name)
        if not is_valid:
            print(f"{error_msg}")
            return False

        try:
            namespace = client.V1Namespace(
                metadata=client.V1ObjectMeta(name=name)
            )
            self.v1.create_namespace(namespace)
            print(f"Created namespace: {name}")
            return True
        except ApiException as e:
            if e.status == 409:
                print(f"Namespace {name} already exists")
            else:
                print(f"Error creating namespace: {e}")
            return False

    def delete_namespace(self, name):
        """
        Delete a namespace.

        Args:
            name: Name of the namespace to delete

        Returns:
            True if successful, False otherwise
        """
        is_valid, error_msg = self.validate_namespace_name(name)
        if not is_valid:
            print(f"{error_msg}")
            return False

        try:
            self.v1.delete_namespace(name)
            print(f"Deleted namespace: {name}")
            return True
        except ApiException as e:
            if e.status == 409:
                print(f"Namespace {name} not found")
            else:
                print(f"Error deleting namespace: {e}")
            return False

    def list_namespaces(self):
        """
        List all namespaces.

        Returns:
            List of namespace names
        """
        try:
            namespaces = self.v1.list_namespace()
            namespace_names = [ns.metadata.name for ns in namespaces.items]

            print("Namespaces:")
            for name in namespace_names:
                print(f" - {name}")

            return namespace_names
        except ApiException as e:
            print(f"Error listing namespaces: {e}")
            return []

    def namespace_exists(self, name):
        """
        Check if a namespace exists.

        Args: Name of the namespace to check

        Returns: True if exists, False otherwise
        """
        is_valid, error_msg = self.validate_namespace_name(name)
        if not is_valid:
            print(f"{error_msg}")
            return False

        try:
            self.v1.read_namespace(name)
            return True
        except ApiException as e:
            if e.status == 404:
                return False
            raise

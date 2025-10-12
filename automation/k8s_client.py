"""
Kubernetes client wrapper for namespace management.
"""

import re

from kubernetes import client, config, utils
from kubernetes.client.rest import ApiException
from yaml import safe_load

from automation.template_renderer import render_template


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
        self.apps_v1 = client.AppsV1Api()

    def _validate_k8s_name(
        self, name: str, resource_type: str = "resource"
    ) -> tuple[bool, str | None]:
        """
        Validate Kubernetes resource name (works for namespaces, deployments, services, etc.)

        Args:
            name: Name to validate
            resource_type: Type of resource for error messages (e.g., "namespace", "deployment", etc.)

        Returns:
            tuple: (is_valid: bool, error_message: str or None)
        """
        if not name:
            return False, f"{resource_type.capitalize()} name cannot be empty"

        if len(name) > 63:
            return (
                False,
                f"{resource_type.capitalize()} name too long (max 63 chars, got {len(name)})",
            )

        # Lowercase alphanumeric + hyphens, start/end with alphanumeric
        pattern = r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$"
        if not re.match(pattern, name):
            return False, (
                f"Invalid {resource_type} name. Must be lowercase letters, numbers, "
                "and hyphens only. Must start and end with alphanumeric character."
            )

        return True, None

    def _validate_image_name(self, image: str) -> tuple[bool, str | None]:
        """
        Validate Docker image format according to OCI specification.

        Expected formats:
        - nginx:latest
        - myregistry.com/myrepo:v1.0
        - gcr.io/project-id/image:tag

        Args:
            image: Full image string (registry/name:tag or name:tag)

        Returns:
            tuple: (is_valid: bool, error_message: str or None)
        """
        if not image:
            return False, "Image name cannot be empty"

        if ":" not in image:
            return False, "Image must include a tag (e.g., 'nginx:latest')"

        parts = image.rsplit(":", 1)
        if len(parts) != 2:
            return False, "Invalid image format"

        name_part, tag = parts

        tag_pattern = r"^[a-zA-Z0-9_][a-zA-Z0-9._-]{0,127}$"
        if not re.match(tag_pattern, tag):
            return False, (
                "Invalid tag format. Must start with alphanumeric or underscore, "
                "followed by alphanumeric, dots, underscores, or hyphens (max 128 chars)"
            )

        name_pattern = r"^[a-z0-9]+((\.|_|__|-+)[a-z0-9]+)*(\/[a-z0-9]+((\.|_|__|-+)[a-z0-9]+)*)*$"

        # Handle registry URLs
        if "/" in name_part:
            registry_host, repo_path = name_part.split("/", 1)

            if not re.match(name_pattern, repo_path):
                return False, (
                    "Invalid repository name format. Must be lowercase alphanumeric "
                    "with dots, underscores, double underscores, or hyphens as separators"
                )
        # No registry, just repository name
        else:
            if not re.match(name_pattern, name_part):
                return False, (
                    "Invalid image name format. Must be lowercase alphanumeric "
                    "with dots, underscores, double underscores, or hyphens as separators"
                )

        if len(image) > 255:
            return False, f"Image reference too long ({len(image)} chars, recommended max 255)"

        return True, None

    def _validate_port(self, port: int) -> tuple[bool, str | None]:
        """
        Validate port number.

        Args:
            port: Port number

        Returns:
            tuple: (is_valid: bool, error_message: str or None)
        """
        if not isinstance(port, int):
            return False, f"Port must be an integer, got {type(port).__name__}"

        if not (1 <= port <= 65535):
            return False, f"Port must be between 1-65535, got {port}"

        return True, None

    def _apply_yaml(self, yaml_content: str, namespace: str) -> bool:
        """
        Apply YAML manifest to Kubernetes cluster.

        Args:
            yaml_content: YAML string to apply
            namespace: Namespace to apply resources to

        Returns:
            True if successful, False otherwise
        """
        try:
            manifest = safe_load(yaml_content)

            # Ensure namespace is set in metadata
            if "metadata" not in manifest:
                manifest["metadata"] = {}
            manifest["metadata"]["namespace"] = namespace

            utils.create_from_dict(self.v1.api_client, manifest)

            kind = manifest.get("kind", "Resource")
            name = manifest.get("metadata", {}).get("name", "unknown")
            print(f"Applied {kind}: {name} in {namespace}")
            return True

        except ApiException:
            print("Error applying YAML to Kubernetes")
            return False
        except Exception:
            print("Error parsing or applying YAML")
            return False

    def create_namespace(self, name: str) -> bool:
        """
        Create a namespace.

        Args:
            name: Name of the namespace to create

        Returns:
            True if successful, False otherwise
        """
        is_valid, error_msg = self._validate_k8s_name(name, "namespace")
        if not is_valid:
            print(error_msg)
            return False

        try:
            namespace = client.V1Namespace(metadata=client.V1ObjectMeta(name=name))
            self.v1.create_namespace(namespace)
            print(f"Created namespace: {name}")
            return True
        except ApiException as e:
            if e.status == 409:
                print(f"Namespace {name} already exists")
            else:
                print(f"Error creating namespace: {e}")
            return False

    def delete_namespace(self, name: str) -> bool:
        """
        Delete a namespace.

        Args:
            name: Name of the namespace to delete

        Returns:
            True if successful, False otherwise
        """
        is_valid, error_msg = self._validate_k8s_name(name, "namespace")
        if not is_valid:
            print(error_msg)
            return False

        try:
            self.v1.delete_namespace(name)
            print(f"Deleted namespace: {name}")
            return True
        except ApiException as e:
            if e.status == 404:
                print(f"Namespace {name} not found")
            else:
                print(f"Error deleting namespace: {e}")
            return False

    def list_namespaces(self) -> list[str]:
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

    def namespace_exists(self, name: str) -> bool:
        """
        Check if a namespace exists.

        Args:
            name: Name of the namespace to check

        Returns:
            True if exists, False otherwise
        """
        is_valid, error_msg = self._validate_k8s_name(name, "namespace")
        if not is_valid:
            print(error_msg)
            return False

        try:
            self.v1.read_namespace(name)
            return True
        except ApiException as e:
            if e.status == 404:
                return False
            raise

    def create_deployment(
        self,
        name: str,
        namespace: str,
        image: str,
        port: int,
        template_dir: str,
        env_vars: dict[str, str] | None = None,
    ) -> bool:
        """
        Create a deployment using templates.

        Args:
            name: Name of the container to deploy
            namespace: Namespace for the container
            image: Name of the image for the container
            port: Port to expose on the pod's IP address
            env_vars: Optional dict of environment variables
            template_dir: Directory containing templates (default: automation/templates/)

        Returns:
            True if successful, False otherwise
        """
        is_valid, error_msg = self._validate_k8s_name(name, "deployment")
        if not is_valid:
            print(error_msg)
            return False

        is_valid, error_msg = self._validate_k8s_name(namespace, "namespace")
        if not is_valid:
            print(error_msg)
            return False

        is_valid, error_msg = self._validate_image_name(image)
        if not is_valid:
            print(error_msg)
            return False

        is_valid, error_msg = self._validate_port(port)
        if not is_valid:
            print(error_msg)
            return False

        data = {
            "name": name,
            "namespace": namespace,
            "image": image,
            "port": port,
            "env_vars": env_vars,
        }

        yaml_content = render_template("deployment.yaml.j2", data, template_dir)
        if not yaml_content:
            return False

        return self._apply_yaml(yaml_content, namespace)

    def create_service(
        self, name: str, namespace: str, port: int, target_port: int, template_dir: str
    ) -> bool:
        """
        Create a service using templates.

        The service routes traffic to pods with the label 'app=<name>'

        Args:
            name: Name of the service (should match deployment name for selector to work)
            namespace: Namespace where the service will be created
            port: Port the service listens on (external port)
            target_port: Port on the pod to forward traffic to (container port)
            template_dir: Directory containing templates (default: templates/)

        Returns:
            True if successful, False otherwise
        """
        is_valid, error_msg = self._validate_k8s_name(name, "service")
        if not is_valid:
            print(error_msg)
            return False

        is_valid, error_msg = self._validate_k8s_name(namespace, "namespace")
        if not is_valid:
            print(error_msg)
            return False

        is_valid, error_msg = self._validate_port(port)
        if not is_valid:
            print(f"Invalid service port: {error_msg}")
            return False

        is_valid, error_msg = self._validate_port(target_port)
        if not is_valid:
            print(f"Invalid target port: {error_msg}")
            return False

        data = {"name": name, "namespace": namespace, "port": port, "target_port": target_port}

        yaml_content = render_template("service.yaml.j2", data, template_dir)
        if not yaml_content:
            return False

        return self._apply_yaml(yaml_content, namespace)

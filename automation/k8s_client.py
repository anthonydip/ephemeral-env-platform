"""
Kubernetes client wrapper for namespace management.
"""

from __future__ import annotations

import re

from kubernetes import client, config, utils
from kubernetes.client.rest import ApiException
from yaml import safe_load

from automation.logger import get_logger
from automation.template_renderer import render_template

logger = get_logger(__name__)


class KubernetesClient:
    """
    Wrapper for Kubernetes API operations.
    """

    def __init__(self):
        """
        Initialize Kubernetes client.
        """
        try:
            # Load kubeconfig from default location (~/.kube/config)
            config.load_kube_config()
            self.v1 = client.CoreV1Api()
            self.apps_v1 = client.AppsV1Api()
            logger.info("Kubernetes client initialized successfully")
        except Exception as e:
            logger.critical(f"Failed to initialize Kubernetes client: {e}")
            raise

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
            error = f"{resource_type.captialize()} name cannot be empty"
            logger.error(error)
            return False, error

        if len(name) > 63:
            error = f"{resource_type.capitalize()} name too long (max 63 chars, got {len(name)})"
            logger.error(error, extra={"name": name, "length": len(name)})
            return False, error

        # Lowercase alphanumeric + hyphens, start/end with alphanumeric
        pattern = r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$"
        if not re.match(pattern, name):
            error = (
                f"Invalid {resource_type} name. Must be lowercase letters, numbers, "
                "and hyphens only. Must start and end with alphanumeric character."
            )
            logger.error(error, extra={"name": name})
            return False, error

        logger.debug(f"Validated {resource_type} name: {name}")
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
            error = "Image name cannot be empty"
            logger.error(error)
            return False, error

        if ":" not in image:
            error = "Image must include a tag (e.g., 'nginx:latest')"
            logger.error(error)
            return False, error

        parts = image.rsplit(":", 1)
        if len(parts) != 2:
            error = "Invalid image format"
            logger.error(error)
            return False, error

        name_part, tag = parts

        tag_pattern = r"^[a-zA-Z0-9_][a-zA-Z0-9._-]{0,127}$"
        if not re.match(tag_pattern, tag):
            error = (
                "Invalid tag format. Must start with alphanumeric or underscore, "
                "followed by alphanumeric, dots, underscores, or hyphens (max 128 chars)"
            )
            logger.error(error, extra={"image": image, "tag": tag})
            return False, error

        name_pattern = r"^[a-z0-9]+((\.|_|__|-+)[a-z0-9]+)*(\/[a-z0-9]+((\.|_|__|-+)[a-z0-9]+)*)*$"

        # Handle registry URLs
        if "/" in name_part:
            registry_host, repo_path = name_part.split("/", 1)

            if not re.match(name_pattern, repo_path):
                error = (
                    "Invalid repository name format. Must be lowercase alphanumeric "
                    "with dots, underscores, double underscores, or hyphens as separators"
                )
                logger.error(error, extra={"image": image, "repo_path": repo_path})
                return False, error
        # No registry, just repository name
        else:
            if not re.match(name_pattern, name_part):
                error = (
                    "Invalid image name format. Must be lowercase alphanumeric "
                    "with dots, underscores, double underscores, or hyphens as separators"
                )
                logger.error(error, extra={"image": image})
                return False, error

        if len(image) > 255:
            error = f"Image reference too long ({len(image)} chars, recommended max 255)"
            logger.warning(error, extra={"image": image})
            return False, error

        logger.debug(f"Validated image: {image}")
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
            error = f"Port must be an integer, got {type(port).__name__}"
            logger.error(error, extra={"port": port, "type": type(port).__name__})
            return False, error

        if not (1 <= port <= 65535):
            error = f"Port must be between 1-65535, got {port}"
            logger.error(error, extra={"port": port})
            return False, error

        logger.debug(f"Validated port: {port}")
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
            logger.info(
                f"Applied {kind}: {name}",
                extra={"kind": kind, "name": name, "namespace": namespace},
            )
            return True

        except ApiException as e:
            logger.error(
                "Kubernetes API error applying YAML",
                extra={"namespace": namespace, "status": e.status, "reason": e.reason},
            )
            return False
        except Exception as e:
            logger.error(f"Error parsing or applying YAML: {e}", extra={"namespace": namespace})
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
            return False

        try:
            namespace = client.V1Namespace(metadata=client.V1ObjectMeta(name=name))
            self.v1.create_namespace(namespace)
            logger.info(f"Created namespace: {name}", extra={"namespace": name})
            return True
        except ApiException as e:
            if e.status == 409:
                logger.warning(f"Namespace {name} already exists", extra={"namespace": name})
            else:
                logger.error(
                    f"Error creating namespace: {e}",
                    extra={"namespace": name, "status": e.status, "reason": e.reason},
                )
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
            return False

        try:
            self.v1.delete_namespace(name)
            logger.info(f"Deleted namespace: {name}", extra={"namespace": name})
            return True
        except ApiException as e:
            if e.status == 404:
                logger.warning(f"Namespace {name} not found", extra={"namespace": name})
            else:
                logger.error(
                    f"Error deleting namespace: {e}",
                    extra={"namespace": name, "status": e.status, "reason": e.reason},
                )
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
            logger.info(f"Listed {len(namespace_names)} namespaces")
            logger.debug(f"Namespaces: {', '.join(namespace_names)}")
            return namespace_names
        except ApiException as e:
            logger.error(f"Error listing namespaces: {e}", extra={"status": e.status})
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
            return False

        try:
            self.v1.read_namespace(name)
            logger.debug(f"Namespace {name} exists")
            return True
        except ApiException as e:
            if e.status == 404:
                logger.debug(f"Namespace {name} does not exist")
                return False
            logger.error(f"Error checking namespace existence: {e}")
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
        logger.info(
            f"Creating deployment: {name}",
            extra={"deployment": name, "namespace": namespace, "image": image, "port": port},
        )

        is_valid, error_msg = self._validate_k8s_name(name, "deployment")
        if not is_valid:
            return False

        is_valid, error_msg = self._validate_k8s_name(namespace, "namespace")
        if not is_valid:
            return False

        is_valid, error_msg = self._validate_image_name(image)
        if not is_valid:
            return False

        is_valid, error_msg = self._validate_port(port)
        if not is_valid:
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
        logger.info(
            f"Creating service: {name}",
            extra={
                "service": name,
                "namespace": namespace,
                "port": port,
                "target_port": target_port,
            },
        )

        is_valid, error_msg = self._validate_k8s_name(name, "service")
        if not is_valid:
            return False

        is_valid, error_msg = self._validate_k8s_name(namespace, "namespace")
        if not is_valid:
            return False

        is_valid, error_msg = self._validate_port(port)
        if not is_valid:
            logger.error("Invalid service port", extra={"port": port})
            return False

        is_valid, error_msg = self._validate_port(target_port)
        if not is_valid:
            logger.error("Invalid target port", extra={"target_port": target_port})
            return False

        data = {"name": name, "namespace": namespace, "port": port, "target_port": target_port}

        yaml_content = render_template("service.yaml.j2", data, template_dir)
        if not yaml_content:
            return False

        return self._apply_yaml(yaml_content, namespace)

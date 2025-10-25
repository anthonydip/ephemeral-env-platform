"""
Kubernetes client wrapper for namespace management.
"""

from __future__ import annotations

import re

from kubernetes import client, config, utils
from kubernetes.client.rest import ApiException
from kubernetes.utils import FailToCreateError
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
            error = f"{resource_type.capitalize()} name cannot be empty"
            logger.error(error)
            return False, error

        if len(name) > 63:
            error = f"{resource_type.capitalize()} name too long (max 63 chars, got {len(name)})"
            logger.error(error, extra={"resource_name": name, "length": len(name)})
            return False, error

        # Lowercase alphanumeric + hyphens, start/end with alphanumeric
        pattern = r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$"
        if not re.match(pattern, name):
            error = (
                f"Invalid {resource_type} name. Must be lowercase letters, numbers, "
                "and hyphens only. Must start and end with alphanumeric character."
            )
            logger.error(error, extra={"resource_name": name})
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
            logger.error(error, extra={"image": image})
            return False, error

        if ":" not in image:
            error = "Image must include a tag (e.g., 'nginx:latest')"
            logger.error(error, extra={"image": image})
            return False, error

        parts = image.rsplit(":", 1)
        if len(parts) != 2:
            error = "Invalid image format"
            logger.error(error, extra={"image": image})
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

    def _parse_yaml_manifest(self, yaml_content: str, namespace: str) -> dict | None:
        """
        Parse YAML content and ensure namespace is set.

        Args:
            yaml_content: YAML string to parse
            namespace: Namespace to set in manifest

        Returns:
            Parsed manifest dict, or None on error
        """
        try:
            manifest = safe_load(yaml_content)

            # Ensure namespace is set in metadata
            if "metadata" not in manifest:
                manifest["metadata"] = {}
            manifest["metadata"]["namespace"] = namespace

            return manifest
        except Exception as e:
            logger.error(f"Error parsing YAML: {e}", extra={"namespace": namespace})
            return None

    def _is_traefik_crd(self, manifest: dict) -> bool:
        """
        Check if manifest is a Traefik Custom Resource Definition.

        Args:
            manifest: Parsed Kubernetes manifest

        Returns:
            True if Traefik CRD, False otherwise
        """
        api_version = manifest.get("apiVersion", "")
        return "traefik.io" in api_version or "traefik.containo.us" in api_version

    def _apply_traefik_crd(self, manifest: dict, namespace: str) -> bool:
        """
        Apply Traefik Custom Resource with create-or-update logic.

        Args:
            manifest: Traefik CRD manifest
            namespace: Namespace to apply to

        Returns:
            True if successful, False otherwise
        """
        kind = manifest.get("kind", "Resource")
        api_version = manifest.get("apiVersion", "")
        resource_name = manifest.get("metadata", {}).get("name", "unknown")

        try:
            custom_api = client.CustomObjectsApi()
            group, version = api_version.split("/")
            plural = kind.lower() + "s"

            # Try to create the resource
            try:
                custom_api.create_namespaced_custom_object(
                    group=group,
                    version=version,
                    namespace=namespace,
                    plural=plural,
                    body=manifest,
                )
                logger.info(
                    f"Created {kind}: {resource_name}",
                    extra={
                        "kind": kind,
                        "resource_name": resource_name,
                        "namespace": namespace,
                    },
                )
                return True
            except ApiException as e:
                if e.status == 409:
                    # Resource already exists, update it
                    return self._update_traefik_crd(
                        custom_api, group, version, namespace, plural, resource_name, manifest
                    )
                else:
                    logger.error(
                        f"Kubernetes API error creating {kind}",
                        extra={
                            "kind": kind,
                            "resource_name": resource_name,
                            "namespace": namespace,
                        },
                    )
                    return False
        except Exception as e:
            logger.error(
                f"Error applying Traefik CRD: {e}", extra={"kind": kind, "namespace": namespace}
            )
            return False

    def _update_traefik_crd(
        self,
        custom_api: client.CustomObjectsApi,
        group: str,
        version: str,
        namespace: str,
        plural: str,
        name: str,
        manifest: dict,
    ) -> bool:
        """
        Update an existing Traefik CRD with proper resourceVersion.

        Args:
            custom_api: CustomObjectsApi instance
            group: API group
            version: API version
            namespace: Namespace
            plural: Resource plural name
            name: Resource name
            manifest: Updated manifest

        Returns:
            True if successful, False otherwise
        """
        kind = manifest.get("kind", "Resource")

        try:
            logger.info(
                f"{kind} {name} already exists, updating...",
                extra={"kind": kind, "resource_name": name, "namespace": namespace},
            )

            # Fetch current resource to get resourceVersion
            current = custom_api.get_namespaced_custom_object(
                group=group,
                version=version,
                namespace=namespace,
                plural=plural,
                name=name,
            )

            # Inject resourceVersion for update
            manifest["metadata"]["resourceVersion"] = current["metadata"]["resourceVersion"]

            # Perform the update
            custom_api.patch_namespaced_custom_object(
                group=group,
                version=version,
                namespace=namespace,
                plural=plural,
                name=name,
                body=manifest,
            )

            logger.info(
                f"Updated {kind}: {name}",
                extra={"kind": kind, "resource_name": name, "namespace": namespace},
            )
            return True
        except ApiException as e:
            logger.error(
                f"Failed to update {kind}: {e}",
                extra={"kind": kind, "resource_name": name, "namespace": namespace},
            )
            return False

    def _apply_standard_resource(self, manifest: dict, namespace: str) -> bool:
        """
        Apply standard Kubernetes resource with create-or-update logic.

        Handles Deployments, Services, Ingress, etc.

        Args:
            manifest: Kubernetes resource manifest
            namespace: Namespace to apply to

        Returns:
            True if successful, False otherwise
        """
        kind = manifest.get("kind", "Resource")
        resource_name = manifest.get("metadata", {}).get("name", "unknown")

        try:
            # Try to create the resource
            utils.create_from_dict(self.v1.api_client, manifest)
            logger.info(
                f"Created {kind}: {resource_name}",
                extra={"kind": kind, "resource_name": resource_name, "namespace": namespace},
            )
            return True
        except FailToCreateError as e:
            error_msg = str(e)
            if "AlreadyExists" in error_msg or "Conflict" in error_msg:
                logger.info(
                    f"{kind} {resource_name} already exists, updating...",
                    extra={
                        "kind": kind,
                        "resource_name": resource_name,
                        "namespace": namespace,
                    },
                )
                return self._update_standard_resource(manifest, namespace, kind, resource_name)
            else:
                logger.error(
                    f"Failed to create {kind}: {e}",
                    extra={
                        "kind": kind,
                        "resource_name": resource_name,
                        "namespace": namespace,
                    },
                )
                return False
        except ApiException as e:
            if e.status == 409:
                # Resource already exists, update it
                logger.info(
                    f"{kind} {resource_name} already exists, updating...",
                    extra={
                        "kind": kind,
                        "resource_name": resource_name,
                        "namespace": namespace,
                    },
                )
                return self._update_standard_resource(manifest, namespace, kind, resource_name)
            else:
                logger.error(
                    "Kubernetes API error applying YAML",
                    extra={
                        "kind": kind,
                        "namespace": namespace,
                        "status": e.status,
                        "reason": e.reason,
                    },
                )
                return False
        except Exception as e:
            logger.error(
                f"Error applying {kind}: {e}", extra={"kind": kind, "namespace": namespace}
            )
            return False

    def _update_standard_resource(
        self, manifest: dict, namespace: str, kind: str, name: str
    ) -> bool:
        """
        Update an existing standard Kubernetes resource.

        Routes to the appropriate API method based on resource kind.

        Args:
            manifest: Resource manifest dict
            namespace: Namespace
            kind: Resource kind (Deployment, Service, Ingress, etc.)
            name: Resource name

        Returns:
            True if successful, False otherwise
        """
        try:
            if kind == "Deployment":
                self.apps_v1.patch_namespaced_deployment(
                    name=name, namespace=namespace, body=manifest
                )
            elif kind == "Service":
                self.v1.patch_namespaced_service(name=name, namespace=namespace, body=manifest)
            elif kind == "Ingress":
                networking_v1 = client.NetworkingV1Api()
                networking_v1.patch_namespaced_ingress(
                    name=name, namespace=namespace, body=manifest
                )
            else:
                logger.warning(
                    f"Update not implemented for kind: {kind}",
                    extra={"kind": kind, "resource_name": name, "namespace": namespace},
                )
                return False

            logger.info(
                f"Updated {kind}: {name}",
                extra={"kind": kind, "resource_name": name, "namespace": namespace},
            )
            return True
        except ApiException as e:
            logger.error(
                f"Failed to update {kind}",
                extra={
                    "kind": kind,
                    "resource_name": name,
                    "namespace": namespace,
                    "status": e.status,
                },
            )
            return False

    def _apply_yaml(self, yaml_content: str, namespace: str) -> bool:
        """
        Apply YAML manifest to Kubernetes cluster.

        Main orchestration method that delegates to specific handlers.

        Args:
            yaml_content: YAML string to apply
            namespace: Namespace to apply resources to

        Returns:
            True if successful, False otherwise
        """
        manifest = self._parse_yaml_manifest(yaml_content, namespace)
        if not manifest:
            return False

        # Route to appropriate handler based on resource type
        if self._is_traefik_crd(manifest):
            return self._apply_traefik_crd(manifest, namespace)
        else:
            return self._apply_standard_resource(manifest, namespace)

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
                return True
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

    def create_middleware(
        self, name: str, namespace: str, prefixes: list[str], template_dir: str
    ) -> bool:
        """
        Create a Traefik Middleware using templates.

        Args:
            name: Name of the middleware
            namespace: Namespace where the middleware will be created
            prefixes: List of path prefixes to strip (e.g., ['/pr-999'])
            template_dir: Directory containing templates

        Returns:
            True if successful, False otherwise
        """
        logger.info(
            f"Creating middleware: {name}",
            extra={"middleware": name, "namespace": namespace, "prefixes": prefixes},
        )

        is_valid, error_msg = self._validate_k8s_name(name, "middleware")
        if not is_valid:
            return False

        is_valid, error_msg = self._validate_k8s_name(namespace, "namespace")
        if not is_valid:
            return False

        data = {"name": name, "namespace": namespace, "prefixes": prefixes}

        yaml_content = render_template("middleware.yaml.j2", data, template_dir)
        if not yaml_content:
            return False

        return self._apply_yaml(yaml_content, namespace)

    def create_ingress(
        self,
        name: str,
        namespace: str,
        path: str,
        service_name: str,
        service_port: int,
        middleware_name: str,
        template_dir: str,
    ) -> bool:
        """
        Create an Ingress resource using templates.

        Args:
            name: Name of the ingress
            namespace: Namespace where the ingress will be created
            path: URL path (e.g., '/pr-999')
            service_name: Backend service name (e.g., 'frontend')
            service_port: Backend service port (e.g., 80)
            middleware_name: Name of the middleware to use (e.g., 'stripprefix')
            template_dir: Directory containing templates

        Returns:
            True if successful, False otherwise
        """
        logger.info(
            f"Creating ingress: {name}",
            extra={
                "ingress": name,
                "namespace": namespace,
                "path": path,
                "service": service_name,
            },
        )

        is_valid, error_msg = self._validate_k8s_name(name, "ingress")
        if not is_valid:
            return False

        is_valid, error_msg = self._validate_k8s_name(namespace, "namespace")
        if not is_valid:
            return False

        is_valid, error_msg = self._validate_port(service_port)
        if not is_valid:
            logger.error("Invalid service port", extra={"service_port": service_port})
            return False

        data = {
            "name": name,
            "namespace": namespace,
            "path": path,
            "service_name": service_name,
            "service_port": service_port,
            "middleware_name": middleware_name,
        }

        yaml_content = render_template("ingress.yaml.j2", data, template_dir)
        if not yaml_content:
            return False

        return self._apply_yaml(yaml_content, namespace)

"""
Kubernetes client wrapper for namespace management.
"""

from __future__ import annotations

import re

from kubernetes import client, config, utils
from kubernetes.client.rest import ApiException
from kubernetes.utils import FailToCreateError
from yaml import safe_load

from automation.constants import (
    DEPLOYMENT_TEMPLATE,
    INGRESS_TEMPLATE,
    MAX_IMAGE_LENGTH,
    MAX_K8S_NAME_LENGTH,
    MAX_PORT,
    MIDDLEWARE_TEMPLATE,
    MIN_PORT,
    SERVICE_TEMPLATE,
)
from automation.exceptions import KubernetesError, ValidationError
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

    def _validate_k8s_name(self, name: str, resource_type: str = "resource") -> None:
        """
        Validate Kubernetes resource name (works for namespaces, deployments, services, etc.)

        Args:
            name: Name to validate
            resource_type: Type of resource for error messages (e.g., "namespace", "deployment", etc.)

        Raises:
            ValidationError: If name is invalid
        """
        if not name:
            raise ValidationError(f"{resource_type.capitalize()} name cannot be empty")

        if len(name) > MAX_K8S_NAME_LENGTH:
            raise ValidationError(
                f"{resource_type.capitalize()} name too long (max {MAX_K8S_NAME_LENGTH} chars, got {len(name)})"
            )

        # Lowercase alphanumeric + hyphens, start/end with alphanumeric
        pattern = r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$"
        if not re.match(pattern, name):
            raise ValidationError(
                f"Invalid {resource_type} name. Must be lowercase letters, numbers, "
                "and hyphens only. Must start and end with alphanumeric character."
            )

        logger.debug(f"Validated {resource_type} name: {name}")

    def _validate_image_name(self, image: str) -> None:
        """
        Validate Docker image format according to OCI specification.

        Expected formats:
        - nginx:latest
        - myregistry.com/myrepo:v1.0
        - gcr.io/project-id/image:tag

        Args:
            image: Full image string (registry/name:tag or name:tag)

        Raises:
            ValidationError: If image is invalid
        """
        if not image:
            raise ValidationError("Image name cannot be empty")

        if ":" not in image:
            raise ValidationError("Image must include a tag (e.g., 'nginx:latest')")

        parts = image.rsplit(":", 1)
        if len(parts) != 2:
            raise ValidationError("Invalid image format")

        name_part, tag = parts

        tag_pattern = r"^[a-zA-Z0-9_][a-zA-Z0-9._-]{0,127}$"
        if not re.match(tag_pattern, tag):
            raise ValidationError(
                "Invalid tag format. Must start with alphanumeric or underscore, "
                "followed by alphanumeric, dots, underscores, or hyphens (max 128 chars)"
            )

        name_pattern = r"^[a-z0-9]+((\.|_|__|-+)[a-z0-9]+)*(\/[a-z0-9]+((\.|_|__|-+)[a-z0-9]+)*)*$"

        # Handle registry URLs
        if "/" in name_part:
            registry_host, repo_path = name_part.split("/", 1)

            if not re.match(name_pattern, repo_path):
                raise ValidationError(
                    "Invalid repository name format. Must be lowercase alphanumeric "
                    "with dots, underscores, double underscores, or hyphens as separators"
                )
        # No registry, just repository name
        else:
            if not re.match(name_pattern, name_part):
                raise ValidationError(
                    "Invalid image name format. Must be lowercase alphanumeric "
                    "with dots, underscores, double underscores, or hyphens as separators"
                )

        if len(image) > MAX_IMAGE_LENGTH:
            raise ValidationError(
                f"Image reference too long ({len(image)} chars, recommended max {MAX_IMAGE_LENGTH})"
            )

        logger.debug(f"Validated image: {image}")

    def _validate_port(self, port: int) -> None:
        """
        Validate port number.

        Args:
            port: Port number

        Raises:
            ValidationError: If port is invalid
        """
        if not isinstance(port, int):
            raise ValidationError(f"Port must be an integer, got {type(port).__name__}")

        if not (MIN_PORT <= port <= MAX_PORT):
            raise ValidationError(f"Port must be between {MIN_PORT}-{MAX_PORT}, got {port}")

        logger.debug(f"Validated port: {port}")

    def _parse_yaml_manifest(self, yaml_content: str, namespace: str) -> dict:
        """
        Parse YAML content and ensure namespace is set.

        Args:
            yaml_content: YAML string to parse
            namespace: Namespace to set in manifest

        Returns:
            Parsed manifest dict

        Raises:
            KubernetesError: If YAML parsing fails
        """
        try:
            manifest = safe_load(yaml_content)

            # Ensure namespace is set in metadata
            if "metadata" not in manifest:
                manifest["metadata"] = {}
            manifest["metadata"]["namespace"] = namespace

            return manifest
        except Exception as e:
            raise KubernetesError(f"Failed to parse YAML manifest: {e}") from e

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

    def _apply_traefik_crd(self, manifest: dict, namespace: str) -> None:
        """
        Apply Traefik Custom Resource with create-or-update logic.

        Args:
            manifest: Traefik CRD manifest
            namespace: Namespace to apply to

        Raises:
            KubernetesError: If operation fails
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
            except ApiException as e:
                if e.status == 409:
                    # Resource already exists, update it
                    self._update_traefik_crd(
                        custom_api, group, version, namespace, plural, resource_name, manifest
                    )
                else:
                    raise KubernetesError(
                        f"Failed to create {kind} {resource_name}: {e.reason}"
                    ) from e
        except KubernetesError:
            raise
        except Exception as e:
            raise KubernetesError(f"Error applying Traefik CRD {kind}: {e}") from e

    def _update_traefik_crd(
        self,
        custom_api: client.CustomObjectsApi,
        group: str,
        version: str,
        namespace: str,
        plural: str,
        name: str,
        manifest: dict,
    ) -> None:
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

        Raises:
            KubernetesError: If update fails
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
        except ApiException as e:
            raise KubernetesError(f"Failed to update {kind} {name}: {e.reason}") from e

    def _apply_standard_resource(self, manifest: dict, namespace: str) -> None:
        """
        Apply standard Kubernetes resource with create-or-update logic.

        Handles Deployments, Services, Ingress, etc.

        Args:
            manifest: Kubernetes resource manifest
            namespace: Namespace to apply to

        Raises:
            KubernetesError: If operation fails
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
        except (FailToCreateError, ApiException) as e:
            is_conflict = False

            if isinstance(e, FailToCreateError):
                is_conflict = "AlreadyExists" in str(e) or "Conflict" in str(e)
            elif isinstance(e, ApiException):
                is_conflict = e.status == 409

            if is_conflict:
                logger.info(
                    f"{kind} {resource_name} already exists, updating...",
                    extra={
                        "kind": kind,
                        "resource_name": resource_name,
                        "namespace": namespace,
                    },
                )
                self._update_standard_resource(manifest, namespace, kind, resource_name)
            else:
                error_msg = f"Failed to apply {kind} {resource_name}"
                if isinstance(e, ApiException):
                    error_msg += f": {e.reason}"
                raise KubernetesError(error_msg) from e
        except KubernetesError:
            raise
        except Exception as e:
            raise KubernetesError(f"Error applying {kind} {resource_name}: {e}") from e

    def _update_standard_resource(
        self, manifest: dict, namespace: str, kind: str, name: str
    ) -> None:
        """
        Update an existing standard Kubernetes resource.

        Routes to the appropriate API method based on resource kind.

        Args:
            manifest: Resource manifest dict
            namespace: Namespace
            kind: Resource kind (Deployment, Service, Ingress, etc.)
            name: Resource name

        Raises:
            KubernetesError: If update fails
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
                raise KubernetesError(f"Update not implemented for resource kind: {kind}")

            logger.info(
                f"Updated {kind}: {name}",
                extra={"kind": kind, "resource_name": name, "namespace": namespace},
            )
        except ApiException as e:
            raise KubernetesError(f"Failed to update {kind} {name}: {e.reason}") from e

    def _apply_yaml(self, yaml_content: str, namespace: str) -> None:
        """
        Apply YAML manifest to Kubernetes cluster.

        Main orchestration method that delegates to specific handlers.

        Args:
            yaml_content: YAML string to apply
            namespace: Namespace to apply resources to

        Raises:
            KubernetesError: If operation fails
        """
        manifest = self._parse_yaml_manifest(yaml_content, namespace)

        # Route to appropriate handler based on resource type
        if self._is_traefik_crd(manifest):
            self._apply_traefik_crd(manifest, namespace)
        else:
            self._apply_standard_resource(manifest, namespace)

    def create_namespace(self, name: str) -> bool:
        """
        Create a namespace.

        Args:
            name: Name of the namespace to create

        Returns:
            True if successful (includes case where namespace already exists)

        Raises:
            ValidationError: If name validation fails
            KubernetesError: If creation fails (except for already exists)
        """
        self._validate_k8s_name(name, "namespace")

        try:
            namespace = client.V1Namespace(metadata=client.V1ObjectMeta(name=name))
            self.v1.create_namespace(namespace)
            logger.info(f"Created namespace: {name}", extra={"namespace": name})
            return True
        except ApiException as e:
            if e.status == 409:
                # Namespace already exists
                logger.info(f"Namespace {name} already exists", extra={"namespace": name})
                return True
            else:
                raise KubernetesError(f"Failed to create namespace {name}: {e.reason}") from e

    def delete_namespace(self, name: str) -> bool:
        """
        Delete a namespace.

        Args:
            name: Name of the namespace to delete

        Returns:
            True if deleted, False if not found

        Raises:
            ValidationError: If name validation fails
            KubernetesError: If deletion fails (except for not found)
        """
        self._validate_k8s_name(name, "namespace")

        try:
            self.v1.delete_namespace(name)
            logger.info(f"Deleted namespace: {name}", extra={"namespace": name})
            return True
        except ApiException as e:
            if e.status == 404:
                # Namespace doesn't exist
                logger.info(
                    f"Namespace {name} not found (already deleted)", extra={"namespace": name}
                )
                return False
            else:
                raise KubernetesError(f"Failed to delete namespace {name}: {e.reason}") from e

    def list_namespaces(self) -> list[str]:
        """
        List all namespaces.

        Returns:
            List of namespace names

        Raises:
            KubernetesError: If listing fails
        """
        try:
            namespaces = self.v1.list_namespace()
            namespace_names = [ns.metadata.name for ns in namespaces.items]
            logger.info(f"Listed {len(namespace_names)} namespaces")
            logger.debug(f"Namespaces: {', '.join(namespace_names)}")
            return namespace_names
        except ApiException as e:
            raise KubernetesError(f"Failed to list namespaces: {e.reason}") from e

    def namespace_exists(self, name: str) -> bool:
        """
        Check if a namespace exists.

        Args:
            name: Name of the namespace to check

        Returns:
            True if exists, False if not found

        Raises:
            ValidationError: If name validation fails
            KubernetesError: If check fails (except for not found)
        """
        self._validate_k8s_name(name, "namespace")

        try:
            self.v1.read_namespace(name)
            logger.debug(f"Namespace {name} exists")
            return True
        except ApiException as e:
            if e.status == 404:
                logger.debug(f"Namespace {name} does not exist")
                return False
            raise KubernetesError(f"Failed to check namespace existence: {e.reason}") from e

    def create_deployment(
        self,
        name: str,
        namespace: str,
        image: str,
        port: int,
        template_dir: str,
        env_vars: dict[str, str] | None = None,
    ) -> None:
        """
        Create a deployment using templates.

        Args:
            name: Name of the container to deploy
            namespace: Namespace for the container
            image: Name of the image for the container
            port: Port to expose on the pod's IP address
            env_vars: Optional dict of environment variables
            template_dir: Directory containing templates (default: automation/templates/)

        Raises:
            ValidationError: If input validation fails
            TemplateError: If template rendering fails
            KubernetesError: If deployment creation fails
        """
        logger.info(
            f"Creating deployment: {name}",
            extra={"deployment": name, "namespace": namespace, "image": image, "port": port},
        )

        self._validate_k8s_name(name, "deployment")
        self._validate_k8s_name(namespace, "namespace")
        self._validate_image_name(image)
        self._validate_port(port)

        data = {
            "name": name,
            "namespace": namespace,
            "image": image,
            "port": port,
            "env_vars": env_vars,
        }

        yaml_content = render_template(DEPLOYMENT_TEMPLATE, data, template_dir)
        self._apply_yaml(yaml_content, namespace)

    def create_service(
        self, name: str, namespace: str, port: int, target_port: int, template_dir: str
    ) -> None:
        """
        Create a service using templates.

        The service routes traffic to pods with the label 'app=<name>'

        Args:
            name: Name of the service (should match deployment name for selector to work)
            namespace: Namespace where the service will be created
            port: Port the service listens on (external port)
            target_port: Port on the pod to forward traffic to (container port)
            template_dir: Directory containing templates (default: templates/)

        Raises:
            ValidationError: If input validation fails
            TemplateError: If template rendering fails
            KubernetesError: If service creation fails
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

        self._validate_k8s_name(name, "service")
        self._validate_k8s_name(namespace, "namespace")
        self._validate_port(port)
        self._validate_port(target_port)

        data = {"name": name, "namespace": namespace, "port": port, "target_port": target_port}

        yaml_content = render_template(SERVICE_TEMPLATE, data, template_dir)
        self._apply_yaml(yaml_content, namespace)

    def create_middleware(
        self, name: str, namespace: str, prefixes: list[str], template_dir: str
    ) -> None:
        """
        Create a Traefik Middleware using templates.

        Args:
            name: Name of the middleware
            namespace: Namespace where the middleware will be created
            prefixes: List of path prefixes to strip (e.g., ['/pr-999'])
            template_dir: Directory containing templates

        Raises:
            ValidationError: If input validation fails
            TemplateError: If template rendering fails
            KubernetesError: If middleware creation fails
        """
        logger.info(
            f"Creating middleware: {name}",
            extra={"middleware": name, "namespace": namespace, "prefixes": prefixes},
        )

        self._validate_k8s_name(name, "middleware")
        self._validate_k8s_name(namespace, "namespace")

        data = {"name": name, "namespace": namespace, "prefixes": prefixes}

        yaml_content = render_template(MIDDLEWARE_TEMPLATE, data, template_dir)
        self._apply_yaml(yaml_content, namespace)

    def create_ingress(
        self,
        name: str,
        namespace: str,
        path: str,
        service_name: str,
        service_port: int,
        middleware_name: str,
        template_dir: str,
    ) -> None:
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

        Raises:
            ValidationError: If input validation fails
            TemplateError: If template rendering fails
            KubernetesError: If ingress creation fails
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

        self._validate_k8s_name(name, "ingress")
        self._validate_k8s_name(namespace, "namespace")
        self._validate_port(service_port)

        data = {
            "name": name,
            "namespace": namespace,
            "path": path,
            "service_name": service_name,
            "service_port": service_port,
            "middleware_name": middleware_name,
        }

        yaml_content = render_template(INGRESS_TEMPLATE, data, template_dir)
        self._apply_yaml(yaml_content, namespace)

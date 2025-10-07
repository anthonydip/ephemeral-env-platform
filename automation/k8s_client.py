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
        self.apps_v1 = client.AppsV1Api()

    def _validate_k8s_name(self, name, resource_type="resource"):
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
            return False, f"{resource_type.capitalize()} name too long (max 63 chars, got {len(name)})"

        # Lowercase alphanumeric + hyphens, start/end with alphanumeric
        pattern = r'^[a-z0-9]([-a-z0-9]*[a-z0-9])?$'
        if not re.match(pattern, name):
            return False, (
                f"Invalid {resource_type} name. Must be lowercase letters, numbers, "
                "and hyphens only. Must start and end with alphanumeric character."
            )

        return True, None

    def _validate_image_name(self, image):
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

        if ':' not in image:
            return False, "Image must include a tag (e.g., 'nginx:latest')"

        parts = image.rsplit(':', 1)
        if len(parts) != 2:
            return False, "Invalid image format"

        name_part, tag = parts

        tag_pattern = r'^[a-zA-Z0-9_][a-zA-Z0-9._-]{0,127}$'
        if not re.match(tag_pattern, tag):
            return False, (
                "Invalid tag format. Must start with alphanumeric or underscore, "
                "followed by alphanumeric, dots, underscores, or hyphens (max 128 chars)"
            )

        name_pattern = r'^[a-z0-9]+((\.|_|__|-+)[a-z0-9]+)*(\/[a-z0-9]+((\.|_|__|-+)[a-z0-9]+)*)*$'

        # Handle registry URLs
        if '/' in name_part:
            registry_host, repo_path = name_part.split('/', 1)

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

    def _validate_port(self, port):
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

    def create_namespace(self, name):
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

    def create_deployment(self, name, namespace, image, port):
        """
        Create a deployment with a single container.

        Args:
            name: Name of the container to deploy
            namespace: Namespace for the container
            image: Name of the image for the container
            port: Number of port to expose on the pod's IP address

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

        container = client.V1Container(
            name=name,
            image=image,
            ports=[client.V1ContainerPort(container_port=port)]
        )

        template = client.V1PodTemplateSpec(
            metadata=client.V1ObjectMeta(labels={"app": name}),
            spec=client.V1PodSpec(containers=[container])
        )

        spec = client.V1DeploymentSpec(
            replicas=1,
            selector=client.V1LabelSelector(match_labels={"app": name}),
            template=template
        )

        deployment = client.V1Deployment(
            api_version="apps/v1",
            kind="Deployment",
            metadata=client.V1ObjectMeta(name=name),
            spec=spec
        )

        try:
            self.apps_v1.create_namespaced_deployment(namespace, deployment)
            print(f"Created deployment: {name} in {namespace}")
            return True
        except ApiException as e:
            print(f"Error creating deployment: {e}")
            return False

    def create_service(self, name, namespace, port, target_port):
        """
        Create a service to expose a deployment.

        The service routes traffic to pods with the label 'app=<name>'

        Args:
            name: Name of the service (should match deployment name for selector to work)
            namespace: Namespace where the service will be created
            port: Port the service listens on (external port)
            target_port: Port on the pod to forward traffic to (container port)

        Returns:
            True if successful, False otherwise
        """
        is_valid, error_msg = self._validate_k8s_name(name, "service")
        if not is_valid:
            print(error_msg)
            return False

        is_valid, error_msg = self._validate_k8s_name(name, "namespace")
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

        service = client.V1Service(
            api_version="v1",
            kind="Service",
            metadata=client.V1ObjectMeta(name=name),
            spec=client.V1ServiceSpec(
                selector={"app": name},
                ports=[client.V1ServicePort(
                    port=port,
                    target_port=target_port
                )]
            )
        )

        try:
            self.v1.create_namespaced_service(namespace, service)
            print(f"Created service: {name} in {namespace}")
            return True
        except ApiException as e:
            print(f"Error creating service: {e}")
            return False

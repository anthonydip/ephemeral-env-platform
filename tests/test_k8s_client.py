"""
Tests for k8s_client.py

Includes validation tests and mocked operation tests.
"""

from unittest.mock import Mock, patch

import pytest
from kubernetes.client.rest import ApiException

from automation.k8s_client import KubernetesClient


@pytest.fixture
def mock_k8s_client(monkeypatch):
    """Create a KubernetesClient with mocked Kubernetes connection."""
    # Mock config.load_kube_config() call
    monkeypatch.setattr("automation.k8s_client.config.load_kube_config", Mock())

    # Mock client APIs
    mock_v1 = Mock()
    mock_apps_v1 = Mock()

    monkeypatch.setattr("automation.k8s_client.client.CoreV1Api", Mock(return_value=mock_v1))
    monkeypatch.setattr("automation.k8s_client.client.AppsV1Api", Mock(return_value=mock_apps_v1))

    k8s = KubernetesClient()
    k8s.v1 = mock_v1
    k8s.apps_v1 = mock_apps_v1
    return k8s


# ============================================================================
# VALIDATION TESTS
# ============================================================================


def test_validate_k8s_name_valid(mock_k8s_client):
    """Test validation of valid Kubernetes name."""
    name = "my-app"
    is_valid, error = mock_k8s_client._validate_k8s_name(name, "deployment")

    assert is_valid
    assert error is None


def test_validate_k8s_name_too_long(mock_k8s_client):
    """Test validation rejects too long Kubernetes name."""
    name = "a" * 64

    is_valid, error = mock_k8s_client._validate_k8s_name(name, "deployment")

    assert not is_valid
    assert "too long" in error
    assert "64" in error


def test_validate_k8s_name_invalid_characters(mock_k8s_client):
    """Test validation rejects invalid characters in Kubernetes name."""
    # Must be lowercase alphanumeric + hyphens
    name = "My-app"

    is_valid, error = mock_k8s_client._validate_k8s_name(name, "deployment")

    assert not is_valid
    assert "invalid deployment name" in error.lower()


def test_validate_k8s_name_empty(mock_k8s_client):
    """Test validation rejects missing Kubernetes name."""
    name = ""

    is_valid, error = mock_k8s_client._validate_k8s_name(name, "deployment")

    assert not is_valid
    assert "cannot be empty" in error


def test_validate_port_valid(mock_k8s_client):
    """Test validation of valid Kubernetes port."""
    port = 80

    is_valid, error = mock_k8s_client._validate_port(port)

    assert is_valid
    assert error is None


def test_validate_port_too_large(mock_k8s_client):
    """Test validation rejects large ports."""
    port = 65536

    is_valid, error = mock_k8s_client._validate_port(port)

    assert not is_valid
    assert "65536" in error


def test_validate_port_negative(mock_k8s_client):
    """Test validation rejects negative ports."""
    port = -1

    is_valid, error = mock_k8s_client._validate_port(port)

    assert not is_valid
    assert "-1" in error


def test_validate_port_not_integer(mock_k8s_client):
    """Test validation rejects non-integer ports."""
    port = "80"

    is_valid, error = mock_k8s_client._validate_port(port)

    assert not is_valid
    assert "integer" in error.lower()


def test_validate_image_name_valid(mock_k8s_client):
    """Test validation of valid Kubernetes image name."""
    image = "nginx:latest"

    is_valid, error = mock_k8s_client._validate_image_name(image)

    assert is_valid
    assert error is None


def test_validate_image_name_with_registry(mock_k8s_client):
    """Test validation of valid Kubernetes image name with registry."""
    image = "myregistry.com/team/backend:latest"

    is_valid, error = mock_k8s_client._validate_image_name(image)

    assert is_valid
    assert error is None


def test_validate_image_name_without_tag(mock_k8s_client):
    """Test validation rejects images without tags."""
    image = "nginx"

    is_valid, error = mock_k8s_client._validate_image_name(image)

    assert not is_valid
    assert "must include a tag" in error


def test_validate_image_name_empty(mock_k8s_client):
    """Test validation rejects images with no name."""
    image = ""

    is_valid, error = mock_k8s_client._validate_image_name(image)

    assert not is_valid
    assert "cannot be empty" in error


def test_validate_image_name_invalid_tag_format(mock_k8s_client):
    """Test validation rejects images with invalid tag format."""
    image = "nginx:@invalid!"

    is_valid, error = mock_k8s_client._validate_image_name(image)

    assert not is_valid
    assert "tag format" in error.lower()


def test_validate_image_name_invalid_repo_format(mock_k8s_client):
    """Test validation rejects images with invalid repository format."""
    image = "Myregistry.com/@team/backend:latest"

    is_valid, error = mock_k8s_client._validate_image_name(image)

    assert not is_valid
    assert "invalid repository name format" in error.lower()


def test_validate_image_name_invalid_image_format(mock_k8s_client):
    """Test validation rejects images with invalid image format."""
    image = "Nginx:latest"

    is_valid, error = mock_k8s_client._validate_image_name(image)

    assert not is_valid
    assert "invalid image name format" in error.lower()


def test_validate_image_name_too_long(mock_k8s_client):
    """Test validation rejects too long image names."""
    # 257 characters total
    image = "a" * 250 + ":latest"

    is_valid, error = mock_k8s_client._validate_image_name(image)

    assert not is_valid
    assert "image reference" in error.lower()


# ============================================================================
# NAMESPACE OPERATIONS TESTS
# ============================================================================


def test_create_namespace_success(mock_k8s_client):
    """Test successfully creating a namespace."""
    mock_k8s_client.v1.create_namespace.return_value = Mock()

    result = mock_k8s_client.create_namespace("test-namespace")

    assert result is True
    mock_k8s_client.v1.create_namespace.assert_called_once()


def test_create_namespace_already_exists(mock_k8s_client):
    """Test creating namespace that already exists returns True."""
    mock_k8s_client.v1.create_namespace.side_effect = ApiException(status=409)

    result = mock_k8s_client.create_namespace("existing-namespace")

    assert result is True


def test_create_namespace_api_error(mock_k8s_client):
    """Test creating namespace with API error."""
    mock_k8s_client.v1.create_namespace.side_effect = ApiException(status=500)

    result = mock_k8s_client.create_namespace("test-namespace")

    assert result is False


def test_create_namespace_invalid_name(mock_k8s_client):
    """Test creating namespace with invalid name."""
    result = mock_k8s_client.create_namespace("INVALID-NAME-WITH-CAPS")

    assert result is False
    mock_k8s_client.v1.create_namespace.assert_not_called()


def test_delete_namespace_success(mock_k8s_client):
    """Test successfully deleting a namespace."""
    mock_k8s_client.v1.delete_namespace.return_value = Mock()

    result = mock_k8s_client.delete_namespace("test-namespace")

    assert result is True
    mock_k8s_client.v1.delete_namespace.assert_called_once_with("test-namespace")


def test_delete_namespace_not_found(mock_k8s_client):
    """Test deleting namespace that doesn't exist."""
    mock_k8s_client.v1.delete_namespace.side_effect = ApiException(status=404)

    result = mock_k8s_client.delete_namespace("nonexistent-namespace")

    assert result is False


def test_delete_namespace_api_error(mock_k8s_client):
    """Test deleting namespace with API error."""
    mock_k8s_client.v1.delete_namespace.side_effect = ApiException(status=500)

    result = mock_k8s_client.delete_namespace("test-namespace")

    assert result is False


# ============================================================================
# DEPLOYMENT OPERATIONS TESTS
# ============================================================================


def test_create_deployment_success(mock_k8s_client, template_dir):
    """Test successfully creating a deployment."""
    with patch("automation.k8s_client.utils.create_from_dict") as mock_create:
        mock_create.return_value = Mock()

        result = mock_k8s_client.create_deployment(
            name="test-app",
            namespace="test-ns",
            image="nginx:latest",
            port=80,
            template_dir=template_dir,
        )

    assert result is True
    mock_create.assert_called_once()


def test_create_deployment_already_exists_updates(mock_k8s_client, template_dir):
    """Test that creating an existing deployment triggers update."""
    with patch("automation.k8s_client.utils.create_from_dict") as mock_create:
        api_exception = ApiException(status=409)
        api_exception.reason = "Conflict"
        mock_create.side_effect = api_exception

        mock_k8s_client.apps_v1.patch_namespaced_deployment.return_value = Mock()

        result = mock_k8s_client.create_deployment(
            name="test-app",
            namespace="test-ns",
            image="nginx:latest",
            port=80,
            template_dir=template_dir,
        )

    assert result is True
    mock_k8s_client.apps_v1.patch_namespaced_deployment.assert_called_once()


def test_create_deployment_invalid_image(mock_k8s_client, template_dir):
    """Test creating deployment with invalid image."""
    result = mock_k8s_client.create_deployment(
        name="test-app", namespace="test-ns", image="", port=80, template_dir=template_dir
    )

    assert result is False


def test_create_deployment_invalid_port(mock_k8s_client, template_dir):
    """Test creating deployment with invalid port."""
    result = mock_k8s_client.create_deployment(
        name="test-app",
        namespace="test-ns",
        image="nginx:latest",
        port=99999,
        template_dir=template_dir,
    )

    assert result is False


def test_create_deployment_missing_template(mock_k8s_client, template_dir):
    """Test creating deployment with missing template file."""
    result = mock_k8s_client.create_deployment(
        name="test-app",
        namespace="test-ns",
        image="nginx:latest",
        port=80,
        template_dir="nonexistent/directory",
    )

    assert result is False


# ============================================================================
# SERVICE OPERATIONS TESTS
# ============================================================================


def test_create_service_success(mock_k8s_client, template_dir):
    """Test successfully creating a service."""
    with patch("automation.k8s_client.utils.create_from_dict") as mock_create:
        mock_create.return_value = Mock()

        result = mock_k8s_client.create_service(
            name="test-svc",
            namespace="test-ns",
            port=80,
            target_port=8080,
            template_dir=template_dir,
        )

    assert result is True
    mock_create.assert_called_once()


def test_create_service_invalid_port(mock_k8s_client, template_dir):
    """Test creating service with invalid port."""
    result = mock_k8s_client.create_service(
        name="test-svc", namespace="test-ns", port=99999, target_port=80, template_dir=template_dir
    )

    assert result is False


# ============================================================================
# MIDDLEWARE OPERATIONS TESTS
# ============================================================================


def test_create_middleware_success(mock_k8s_client, template_dir):
    """Test successfully creating Traefik middleware."""
    mock_custom_api = Mock()
    mock_custom_api.create_namespaced_custom_object.return_value = Mock()

    with patch("automation.k8s_client.client.CustomObjectsApi", return_value=mock_custom_api):
        result = mock_k8s_client.create_middleware(
            name="stripprefix", namespace="test-ns", prefixes=["/pr-123"], template_dir=template_dir
        )

    assert result is True
    mock_custom_api.create_namespaced_custom_object.assert_called_once()


# ============================================================================
# INGRESS OPERATIONS TESTS
# ============================================================================


def test_create_ingress_success(mock_k8s_client, template_dir):
    """Test successfully creating ingress."""
    with patch("automation.k8s_client.utils.create_from_dict") as mock_create:
        mock_create.return_value = Mock()

        result = mock_k8s_client.create_ingress(
            name="test-ingress",
            namespace="test-ns",
            path="/test",
            service_name="test-svc",
            service_port=80,
            middleware_name="stripprefix",
            template_dir=template_dir,
        )

    assert result is True


# ============================================================================
# YAML PARSING AND ROUTING TESTS
# ============================================================================


def test_parse_yaml_manifest_success(mock_k8s_client):
    """Test successfully parsing YAML manifest."""
    yaml_content = """
apiVersion: v1
kind: Service
metadata:
  name: test-service
spec:
  ports:
  - port: 80
"""

    result = mock_k8s_client._parse_yaml_manifest(yaml_content, "test-ns")

    assert result is not None
    assert result["kind"] == "Service"
    assert result["metadata"]["name"] == "test-service"
    assert result["metadata"]["namespace"] == "test-ns"


def test_parse_yaml_manifest_invalid_yaml(mock_k8s_client):
    """Test parsing invalid YAML returns None."""
    yaml_content = "invalid: yaml: content: [[[["

    result = mock_k8s_client._parse_yaml_manifest(yaml_content, "test-ns")

    assert result is None


def test_is_traefik_crd_with_traefik_io(mock_k8s_client):
    """Test detection of Traefik CRD with traefik.io apiVersion."""
    manifest = {
        "apiVersion": "traefik.io/v1alpha1",
        "kind": "Middleware",
        "metadata": {"name": "test"},
    }

    result = mock_k8s_client._is_traefik_crd(manifest)

    assert result is True


def test_is_traefik_crd_with_traefik_containo_us(mock_k8s_client):
    """Test detection of Traefik CRD with traefik.containo.us apiVersion."""
    manifest = {
        "apiVersion": "traefik.containo.us/v1alpha1",
        "kind": "IngressRoute",
        "metadata": {"name": "test"},
    }

    result = mock_k8s_client._is_traefik_crd(manifest)

    assert result is True


def test_is_traefik_crd_with_standard_resource(mock_k8s_client):
    """Test that standard Kubernetes resources are not detected as Traefik CRDs."""
    manifest = {"apiVersion": "v1", "kind": "Service", "metadata": {"name": "test"}}

    result = mock_k8s_client._is_traefik_crd(manifest)

    assert result is False


def test_is_traefik_crd_with_apps_v1(mock_k8s_client):
    """Test that apps/v1 resources are not detected as Traefik CRDs."""
    manifest = {"apiVersion": "apps/v1", "kind": "Deployment", "metadata": {"name": "test"}}

    result = mock_k8s_client._is_traefik_crd(manifest)

    assert result is False


def test_apply_traefik_crd_create_success(mock_k8s_client):
    """Test successfully creating a new Traefik CRD."""
    manifest = {
        "apiVersion": "traefik.io/v1alpha1",
        "kind": "Middleware",
        "metadata": {"name": "test-middleware", "namespace": "test-ns"},
    }

    mock_custom_api = Mock()
    mock_custom_api.create_namespaced_custom_object.return_value = Mock()

    with patch("automation.k8s_client.client.CustomObjectsApi", return_value=mock_custom_api):
        result = mock_k8s_client._apply_traefik_crd(manifest, "test-ns")

    assert result is True
    mock_custom_api.create_namespaced_custom_object.assert_called_once()


def test_apply_traefik_crd_already_exists_updates(mock_k8s_client):
    """Test that existing Traefik CRD is updated."""
    manifest = {
        "apiVersion": "traefik.io/v1alpha1",
        "kind": "Middleware",
        "metadata": {"name": "test-middleware", "namespace": "test-ns"},
    }

    mock_custom_api = Mock()

    api_exception = ApiException(status=409)
    mock_custom_api.create_namespaced_custom_object.side_effect = api_exception

    mock_custom_api.get_namespaced_custom_object.return_value = {
        "metadata": {"resourceVersion": "12345"}
    }
    mock_custom_api.patch_namespaced_custom_object.return_value = Mock()

    with patch("automation.k8s_client.client.CustomObjectsApi", return_value=mock_custom_api):
        result = mock_k8s_client._apply_traefik_crd(manifest, "test-ns")

    assert result is True

    mock_custom_api.get_namespaced_custom_object.assert_called_once()
    mock_custom_api.patch_namespaced_custom_object.assert_called_once()


def test_apply_standard_resource_create_success(mock_k8s_client):
    """Test successfully creating a standard Kubernetes resource."""
    manifest = {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {"name": "test-service", "namespace": "test-ns"},
    }

    with patch("automation.k8s_client.utils.create_from_dict") as mock_create:
        mock_create.return_value = Mock()

        result = mock_k8s_client._apply_standard_resource(manifest, "test-ns")

    assert result is True
    mock_create.assert_called_once()


def test_apply_standard_resource_already_exists_updates(mock_k8s_client):
    """Test that existing standard resource is updated."""
    manifest = {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {"name": "test-deployment", "namespace": "test-ns"},
    }

    with patch("automation.k8s_client.utils.create_from_dict") as mock_create:
        api_exception = ApiException(status=409)
        api_exception.reason = "Conflict"
        mock_create.side_effect = api_exception

        mock_k8s_client.apps_v1.patch_namespaced_deployment.return_value = Mock()

        result = mock_k8s_client._apply_standard_resource(manifest, "test-ns")

    assert result is True
    mock_k8s_client.apps_v1.patch_namespaced_deployment.assert_called_once()


def test_update_standard_resource_deployment(mock_k8s_client):
    """Test updating a Deployment resource."""
    manifest = {"apiVersion": "apps/v1", "kind": "Deployment", "metadata": {"name": "test-app"}}

    mock_k8s_client.apps_v1.patch_namespaced_deployment.return_value = Mock()

    result = mock_k8s_client._update_standard_resource(
        manifest, "test-ns", "Deployment", "test-app"
    )

    assert result is True
    mock_k8s_client.apps_v1.patch_namespaced_deployment.assert_called_once_with(
        name="test-app", namespace="test-ns", body=manifest
    )


def test_update_standard_resource_service(mock_k8s_client):
    """Test updating a Service resource."""
    manifest = {"apiVersion": "v1", "kind": "Service", "metadata": {"name": "test-svc"}}

    mock_k8s_client.v1.patch_namespaced_service.return_value = Mock()

    result = mock_k8s_client._update_standard_resource(manifest, "test-ns", "Service", "test-svc")

    assert result is True
    mock_k8s_client.v1.patch_namespaced_service.assert_called_once_with(
        name="test-svc", namespace="test-ns", body=manifest
    )


def test_update_standard_resource_ingress(mock_k8s_client):
    """Test updating an Ingress resource."""
    manifest = {
        "apiVersion": "networking.k8s.io/v1",
        "kind": "Ingress",
        "metadata": {"name": "test-ingress"},
    }

    mock_networking_v1 = Mock()
    mock_networking_v1.patch_namespaced_ingress.return_value = Mock()

    with patch("automation.k8s_client.client.NetworkingV1Api", return_value=mock_networking_v1):
        result = mock_k8s_client._update_standard_resource(
            manifest, "test-ns", "Ingress", "test-ingress"
        )

    assert result is True
    mock_networking_v1.patch_namespaced_ingress.assert_called_once()


def test_update_standard_resource_unsupported_kind(mock_k8s_client):
    """Test updating an unsupported resource kind returns False."""
    manifest = {"apiVersion": "v1", "kind": "UnsupportedKind", "metadata": {"name": "test"}}

    result = mock_k8s_client._update_standard_resource(
        manifest, "test-ns", "UnsupportedKind", "test"
    )

    assert result is False


def test_update_standard_resource_api_error(mock_k8s_client):
    """Test update with API error returns False."""
    manifest = {"apiVersion": "v1", "kind": "Service", "metadata": {"name": "test-svc"}}

    mock_k8s_client.v1.patch_namespaced_service.side_effect = ApiException(status=500)

    result = mock_k8s_client._update_standard_resource(manifest, "test-ns", "Service", "test-svc")

    assert result is False

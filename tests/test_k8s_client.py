"""
Tests for k8s_client.py validation methods
"""
import pytest
from unittest.mock import Mock, patch
from automation.k8s_client import KubernetesClient

@pytest.fixture
def mock_k8s_client(monkeypatch):
    """Create a KubernetesClient with mocked Kubernetes connection."""
    # Mock config.load_kube_config() call
    monkeypatch.setattr('automation.k8s_client.config.load_kube_config', Mock())

    # Mock client APIs
    monkeypatch.setattr('automation.k8s_client.client.CoreV1Api', Mock())
    monkeypatch.setattr('automation.k8s_client.client.AppsV1Api', Mock())

    k8s = KubernetesClient()
    return k8s

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

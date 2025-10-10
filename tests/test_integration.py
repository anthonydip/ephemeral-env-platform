"""
Integration tests for k8s_client.py

These tests require a running Kubernetes cluster (Minikube/k3s).

Run with: pytest tests/test_integration.py -v
Skip with: py test tests/ -v -m "not integration"
"""
import pytest
import time
from automation.k8s_client import KubernetesClient

pytestmark = pytest.mark.integration

def wait_for_namespace_deletion(k8s_client, namespace, max_wait=30):
    """
    Wait for namespace to be fully deleted.

    Args:
        k8s_client: KubernetesClient instance
        namespace: Namespace name
        max_wait: Maximum seconds to wait

    Returns:
        True if deleted, False if still exists after max_wait
    """
    wait_interval = 2
    for _ in range(max_wait // wait_interval):
        if not k8s_client.namespace_exists(namespace):
            return True
        time.sleep(wait_interval)
    return False

@pytest.fixture
def k8s_client():
    """Create a real KubernetesClient (requires cluster)."""
    return KubernetesClient()

@pytest.fixture
def test_namespace():
    """Provide a unique test namespace and ensure cleanup."""
    namespace = "test-integration"
    yield namespace

    k8s = KubernetesClient()
    try:
        k8s.delete_namespace(namespace)
        wait_for_namespace_deletion(k8s, namespace, max_wait=30)
    except:
        pass

def test_create_and_delete_namespace(k8s_client, test_namespace):
    """Test creating and deleting a namespace."""
    result = k8s_client.create_namespace(test_namespace)
    assert result
    assert k8s_client.namespace_exists(test_namespace)

    result = k8s_client.delete_namespace(test_namespace)
    assert result

    deleted = wait_for_namespace_deletion(k8s_client, test_namespace, max_wait=30)
    assert deleted, f"Namespace {test_namespace} not deleted after 30 seconds"

def test_create_deployment_without_env(k8s_client, test_namespace):
    """Test creating a deployment without environment variables."""
    k8s_client.create_namespace(test_namespace)

    result = k8s_client.create_deployment(
        name="test-nginx",
        namespace=test_namespace,
        image="nginx:latest",
        port=80,
        template_dir="templates/",
        env_vars=None
    )

    assert result

    deployments = k8s_client.apps_v1.list_namespaced_deployment(test_namespace)
    deployment_names = [d.metadata.name for d in deployments.items]
    assert "test-nginx" in deployment_names

def test_create_deployment_with_env_vars(k8s_client, test_namespace):
    """Test creating a deployment with environment variables."""
    k8s_client.create_namespace(test_namespace)

    result = k8s_client.create_deployment(
        name="test-postgres",
        namespace=test_namespace,
        image="postgres:15",
        port=5432,
        template_dir="templates/",
        env_vars={
            'POSTGRES_PASSWORD': 'testpassword',
            'POSTGRES_USER': 'testuser'
        }
    )

    assert result

    deployments = k8s_client.apps_v1.list_namespaced_deployment(test_namespace)
    deployment_names = [d.metadata.name for d in deployments.items]
    assert "test-postgres" in deployment_names

    deployment = k8s_client.apps_v1.read_namespaced_deployment("test-postgres", test_namespace)
    container = deployment.spec.template.spec.containers[0]
    env_dict = {e.name: e.value for e in container.env}
    assert env_dict['POSTGRES_PASSWORD'] == 'testpassword'
    assert env_dict['POSTGRES_USER'] == 'testuser'

def test_create_service(k8s_client, test_namespace):
    """Test creating a service."""
    k8s_client.create_namespace(test_namespace)

    result = k8s_client.create_service(
        name="test-service",
        namespace=test_namespace,
        port=80,
        target_port=80,
        template_dir="templates/"
    )

    assert result

    services = k8s_client.v1.list_namespaced_service(test_namespace)
    service_names = [s.metadata.name for s in services.items]
    assert "test-service" in service_names

    service = k8s_client.v1.read_namespaced_service("test-service", test_namespace)
    assert service.spec.ports[0].port == 80
    assert service.spec.ports[0].target_port == 80

def test_full_environment_creation(k8s_client, test_namespace):
    """Test creating a full environment (namespace + deployment + service)"""
    assert k8s_client.create_namespace(test_namespace)

    assert k8s_client.create_deployment(
        name="app",
        namespace=test_namespace,
        image="nginx:latest",
        port=80,
        template_dir="templates/",
        env_vars=None
    )

    assert k8s_client.create_service(
        name="app",
        namespace=test_namespace,
        port=80,
        target_port=80,
        template_dir="templates/"
    )

    assert k8s_client.namespace_exists(test_namespace)

    deployments = k8s_client.apps_v1.list_namespaced_deployment(test_namespace)
    deployment_names = [d.metadata.name for d in deployments.items]
    assert "app" in deployment_names

    services = k8s_client.v1.list_namespaced_service(test_namespace)
    service_names = [s.metadata.name for s in services.items]
    assert "app" in service_names

    k8s_client.delete_namespace(test_namespace)

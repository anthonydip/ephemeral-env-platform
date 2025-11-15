"""
Integration tests for k8s_client.py

These tests require a running Kubernetes cluster (Minikube/k3s).

Run with: pytest tests/test_integration.py -v
Skip with: py test tests/ -v -m "not integration"
"""

import time
import uuid

import pytest
from kubernetes import client

from automation.constants import (
    DEFAULT_TEMPLATE_DIR,
    STRIPPREFIX_MIDDLEWARE,
)
from automation.k8s_client import KubernetesClient
from automation.main import create_environment, delete_environment

pytestmark = pytest.mark.integration

MAX_WAIT_FOR_DELETION = 30
WAIT_FOR_DELETION_INTERVAL = 2
MAX_WAIT_FOR_READY = 30
WAIT_FOR_READY_INTERVAL = 3


def wait_for_namespace_deletion(k8s_client, namespace, max_wait=MAX_WAIT_FOR_DELETION):
    """
    Wait for namespace to be fully deleted.

    Args:
        k8s_client: KubernetesClient instance
        namespace: Namespace name
        max_wait: Maximum seconds to wait

    Returns:
        True if deleted, False if still exists after max_wait
    """
    for _ in range(max_wait // WAIT_FOR_DELETION_INTERVAL):
        if not k8s_client.namespace_exists(namespace):
            return True
        time.sleep(WAIT_FOR_DELETION_INTERVAL)
    return False


@pytest.fixture
def k8s_client():
    """Create a real KubernetesClient (requires cluster)."""
    return KubernetesClient()


@pytest.fixture
def test_namespace():
    """Provide a unique test namespace and ensure cleanup."""
    namespace = f"test-integration-{uuid.uuid4().hex[:8]}"
    yield namespace

    k8s = KubernetesClient()
    try:
        k8s.delete_namespace(namespace)
        deleted = wait_for_namespace_deletion(k8s, namespace, max_wait=MAX_WAIT_FOR_DELETION)
        if not deleted:
            pytest.fail(
                f"Namespace {namespace} still exists after {MAX_WAIT_FOR_DELETION}s, cleanup failed"
            )
    except Exception as e:
        print(f"Failed to cleanup namespace {namespace}: {e}")


@pytest.fixture
def test_config_file(tmp_path):
    """Create a temporary test config file for integration tests."""
    config = tmp_path / "integration-test-config.yaml"
    config.write_text(
        """
services:
  - name: frontend
    image: nginx:latest
    port: 80
    ingress:
      enabled: true
      path: "/"
  - name: backend
    image: nginx:alpine
    port: 8080
    ingress:
      enabled: true
      path: "/api"
"""
    )
    return str(config)


def test_create_and_delete_namespace(k8s_client, test_namespace):
    """Test creating and deleting a namespace."""
    result = k8s_client.create_namespace(test_namespace)
    assert result
    assert k8s_client.namespace_exists(test_namespace)

    result = k8s_client.delete_namespace(test_namespace)
    assert result

    deleted = wait_for_namespace_deletion(
        k8s_client, test_namespace, max_wait=MAX_WAIT_FOR_DELETION
    )
    assert deleted, f"Namespace {test_namespace} not deleted after {MAX_WAIT_FOR_DELETION} seconds"


def test_create_deployment_without_env(k8s_client, test_namespace):
    """Test creating a deployment without environment variables."""
    k8s_client.create_namespace(test_namespace)

    k8s_client.create_deployment(
        name="test-nginx",
        namespace=test_namespace,
        image="nginx:latest",
        port=80,
        template_dir=DEFAULT_TEMPLATE_DIR,
        env_vars=None,
    )

    deployments = k8s_client.apps_v1.list_namespaced_deployment(test_namespace)
    deployment_names = [d.metadata.name for d in deployments.items]
    assert "test-nginx" in deployment_names


def test_create_deployment_with_env_vars(k8s_client, test_namespace):
    """Test creating a deployment with environment variables."""
    k8s_client.create_namespace(test_namespace)

    k8s_client.create_deployment(
        name="test-postgres",
        namespace=test_namespace,
        image="postgres:15",
        port=5432,
        template_dir=DEFAULT_TEMPLATE_DIR,
        env_vars={"POSTGRES_PASSWORD": "testpassword", "POSTGRES_USER": "testuser"},
    )

    deployments = k8s_client.apps_v1.list_namespaced_deployment(test_namespace)
    deployment_names = [d.metadata.name for d in deployments.items]
    assert "test-postgres" in deployment_names

    deployment = k8s_client.apps_v1.read_namespaced_deployment("test-postgres", test_namespace)
    container = deployment.spec.template.spec.containers[0]
    env_dict = {e.name: e.value for e in container.env}
    assert env_dict["POSTGRES_PASSWORD"] == "testpassword"
    assert env_dict["POSTGRES_USER"] == "testuser"


def test_create_service(k8s_client, test_namespace):
    """Test creating a service."""
    k8s_client.create_namespace(test_namespace)

    k8s_client.create_service(
        name="test-service",
        namespace=test_namespace,
        port=80,
        target_port=80,
        template_dir=DEFAULT_TEMPLATE_DIR,
    )

    services = k8s_client.v1.list_namespaced_service(test_namespace)
    service_names = [s.metadata.name for s in services.items]
    assert "test-service" in service_names

    service = k8s_client.v1.read_namespaced_service("test-service", test_namespace)
    assert service.spec.ports[0].port == 80
    assert service.spec.ports[0].target_port == 80


def test_basic_environment_creation(k8s_client, test_namespace):
    """Test creating a basic environment (namespace + deployment + service)"""
    k8s_client.create_namespace(test_namespace)

    k8s_client.create_deployment(
        name="app",
        namespace=test_namespace,
        image="nginx:latest",
        port=80,
        template_dir=DEFAULT_TEMPLATE_DIR,
        env_vars=None,
    )

    k8s_client.create_service(
        name="app",
        namespace=test_namespace,
        port=80,
        target_port=80,
        template_dir=DEFAULT_TEMPLATE_DIR,
    )

    assert k8s_client.namespace_exists(test_namespace)

    deployments = k8s_client.apps_v1.list_namespaced_deployment(test_namespace)
    deployment_names = [d.metadata.name for d in deployments.items]
    assert "app" in deployment_names

    services = k8s_client.v1.list_namespaced_service(test_namespace)
    service_names = [s.metadata.name for s in services.items]
    assert "app" in service_names

    k8s_client.delete_namespace(test_namespace)


def test_create_middleware(k8s_client, test_namespace):
    """Test creating a Traefik middleware."""
    k8s_client.create_namespace(test_namespace)

    k8s_client.create_middleware(
        name=STRIPPREFIX_MIDDLEWARE,
        namespace=test_namespace,
        prefixes=[f"/{test_namespace}"],
        template_dir=DEFAULT_TEMPLATE_DIR,
    )

    custom_api = client.CustomObjectsApi()
    try:
        middleware = custom_api.get_namespaced_custom_object(
            group="traefik.io",
            version="v1alpha1",
            namespace=test_namespace,
            plural="middlewares",
            name=STRIPPREFIX_MIDDLEWARE,
        )
        assert middleware["metadata"]["name"] == STRIPPREFIX_MIDDLEWARE
        assert middleware["spec"]["stripPrefix"]["prefixes"][0] == f"/{test_namespace}"
    except Exception as e:
        pytest.fail(f"Middleware not found or invalid: {e}")


def test_create_ingress(k8s_client, test_namespace):
    """Test creating an ingress resource."""
    k8s_client.create_namespace(test_namespace)

    # Create service to route to
    k8s_client.create_service(
        name="test-app",
        namespace=test_namespace,
        port=80,
        target_port=80,
        template_dir=DEFAULT_TEMPLATE_DIR,
    )

    # Create middleware
    k8s_client.create_middleware(
        name=STRIPPREFIX_MIDDLEWARE,
        namespace=test_namespace,
        prefixes=[f"/{test_namespace}"],
        template_dir=DEFAULT_TEMPLATE_DIR,
    )

    # Create ingress
    k8s_client.create_ingress(
        name=f"{test_namespace}-ingress",
        namespace=test_namespace,
        path=f"/{test_namespace}",
        service_name="test-app",
        service_port=80,
        middleware_name=STRIPPREFIX_MIDDLEWARE,
        template_dir=DEFAULT_TEMPLATE_DIR,
    )

    # Verify ingress was created
    networking_v1 = client.NetworkingV1Api()
    ingress = networking_v1.read_namespaced_ingress(
        name=f"{test_namespace}-ingress", namespace=test_namespace
    )

    assert ingress.metadata.name == f"{test_namespace}-ingress"
    assert ingress.spec.rules[0].http.paths[0].path == f"/{test_namespace}"
    assert ingress.spec.rules[0].http.paths[0].backend.service.name == "test-app"
    assert ingress.spec.rules[0].http.paths[0].backend.service.port.number == 80

    # Verify middleware annotation
    expected_middleware = f"{test_namespace}-{STRIPPREFIX_MIDDLEWARE}@kubernetescrd"
    assert (
        ingress.metadata.annotations["traefik.ingress.kubernetes.io/router.middlewares"]
        == expected_middleware
    )


def test_full_stack_with_ingress(k8s_client, test_namespace):
    """Test creating complete environment with ingress routing."""
    k8s_client.create_namespace(test_namespace)

    # Create deployment
    k8s_client.create_deployment(
        name="frontend",
        namespace=test_namespace,
        image="nginx:latest",
        port=80,
        template_dir=DEFAULT_TEMPLATE_DIR,
        env_vars=None,
    )

    # Create service
    k8s_client.create_service(
        name="frontend",
        namespace=test_namespace,
        port=80,
        target_port=80,
        template_dir=DEFAULT_TEMPLATE_DIR,
    )

    # Create middleware
    k8s_client.create_middleware(
        name=STRIPPREFIX_MIDDLEWARE,
        namespace=test_namespace,
        prefixes=[f"/{test_namespace}"],
        template_dir=DEFAULT_TEMPLATE_DIR,
    )

    # Create ingress
    k8s_client.create_ingress(
        name=f"{test_namespace}-frontend-ingress",
        namespace=test_namespace,
        path=f"/{test_namespace}/",
        service_name="frontend",
        service_port=80,
        middleware_name=STRIPPREFIX_MIDDLEWARE,
        template_dir=DEFAULT_TEMPLATE_DIR,
    )

    # Verify all resources exist
    assert k8s_client.namespace_exists(test_namespace)

    deployments = k8s_client.apps_v1.list_namespaced_deployment(test_namespace)
    assert "frontend" in [d.metadata.name for d in deployments.items]

    services = k8s_client.v1.list_namespaced_service(test_namespace)
    assert "frontend" in [s.metadata.name for s in services.items]

    networking_v1 = client.NetworkingV1Api()
    ingresses = networking_v1.list_namespaced_ingress(test_namespace)
    assert f"{test_namespace}-frontend-ingress" in [i.metadata.name for i in ingresses.items]


def test_deployment_pods_become_ready(k8s_client, test_namespace):
    """Test that deployment pods actually start and reach ready state."""
    k8s_client.create_namespace(test_namespace)

    k8s_client.create_deployment(
        name="nginx-app",
        namespace=test_namespace,
        image="nginx:latest",
        port=80,
        template_dir=DEFAULT_TEMPLATE_DIR,
        env_vars=None,
    )

    # Wait for at least one pod to be ready
    for _ in range(MAX_WAIT_FOR_READY // WAIT_FOR_READY_INTERVAL):
        pods = k8s_client.v1.list_namespaced_pod(test_namespace, label_selector="app=nginx-app")

        if pods.items:
            pod = pods.items[0]
            # Check if pod is running and containers are ready
            if (
                pod.status.phase == "Running"
                and pod.status.container_statuses
                and all(cs.ready for cs in pod.status.container_statuses)
            ):
                # Pod is ready
                assert pod.status.phase == "Running"
                assert len(pod.status.container_statuses) > 0
                return

        time.sleep(WAIT_FOR_READY_INTERVAL)

    pytest.fail(f"Deployment pods did not become ready within {MAX_WAIT_FOR_READY} seconds")


def test_namespace_deletion_removes_all_resources(k8s_client, test_namespace):
    """Test that deleting namespace removes all resources."""
    # Create namespace with multiple resources
    k8s_client.create_namespace(test_namespace)

    k8s_client.create_deployment(
        name="app1",
        namespace=test_namespace,
        image="nginx:latest",
        port=80,
        template_dir=DEFAULT_TEMPLATE_DIR,
    )

    k8s_client.create_service(
        name="app1",
        namespace=test_namespace,
        port=80,
        target_port=80,
        template_dir=DEFAULT_TEMPLATE_DIR,
    )

    k8s_client.create_middleware(
        name=STRIPPREFIX_MIDDLEWARE,
        namespace=test_namespace,
        prefixes=[f"/{test_namespace}"],
        template_dir=DEFAULT_TEMPLATE_DIR,
    )

    # Verify resources exist
    assert k8s_client.namespace_exists(test_namespace)
    deployments = k8s_client.apps_v1.list_namespaced_deployment(test_namespace)
    assert len(deployments.items) > 0

    # Delete namespace
    result = k8s_client.delete_namespace(test_namespace)
    assert result

    # Wait for deletion
    deleted = wait_for_namespace_deletion(
        k8s_client, test_namespace, max_wait=MAX_WAIT_FOR_DELETION
    )
    assert deleted, "Namespace not deleted within timeout"

    # Verify namespace is gone
    assert not k8s_client.namespace_exists(test_namespace)


def test_create_namespace_idempotent(k8s_client, test_namespace):
    """Test that creating an existing namespace returns True."""
    # Create namespace
    result1 = k8s_client.create_namespace(test_namespace)
    assert result1
    assert k8s_client.namespace_exists(test_namespace)

    # Creating same namespace should return True
    result2 = k8s_client.create_namespace(test_namespace)
    assert result2
    assert k8s_client.namespace_exists(test_namespace)


def test_create_deployment_updates_existing(k8s_client, test_namespace):
    """Test that recreating a deployment updates it instead of failing."""
    k8s_client.create_namespace(test_namespace)

    # Create deployment with nginx:latest
    k8s_client.create_deployment(
        name="updateable-app",
        namespace=test_namespace,
        image="nginx:latest",
        port=80,
        template_dir=DEFAULT_TEMPLATE_DIR,
    )

    # Verify first deployment
    deployment1 = k8s_client.apps_v1.read_namespaced_deployment("updateable-app", test_namespace)
    assert deployment1.spec.template.spec.containers[0].image == "nginx:latest"

    # Create again with different image, should update
    k8s_client.create_deployment(
        name="updateable-app",
        namespace=test_namespace,
        image="nginx:alpine",
        port=80,
        template_dir=DEFAULT_TEMPLATE_DIR,
    )

    # Verify deployment was updated
    deployment2 = k8s_client.apps_v1.read_namespaced_deployment("updateable-app", test_namespace)
    assert deployment2.spec.template.spec.containers[0].image == "nginx:alpine"


def test_full_workflow_create_environment(k8s_client, test_namespace, test_config_file):
    """Test complete create_environment workflow with real config."""
    # Use create_environment from main.py
    success = create_environment(
        k8s=k8s_client,
        namespace=test_namespace,
        config_path=test_config_file,
        template_dir=DEFAULT_TEMPLATE_DIR,
        github=None,
    )

    assert success, "create_environment should return True"

    # Verify namespace was created
    assert k8s_client.namespace_exists(test_namespace)

    # Verify both services were deployed
    deployments = k8s_client.apps_v1.list_namespaced_deployment(test_namespace)
    deployment_names = [d.metadata.name for d in deployments.items]
    assert "frontend" in deployment_names
    assert "backend" in deployment_names

    # Verify both services exist
    services = k8s_client.v1.list_namespaced_service(test_namespace)
    service_names = [s.metadata.name for s in services.items]
    assert "frontend" in service_names
    assert "backend" in service_names

    # Verify middleware was created
    custom_api = client.CustomObjectsApi()
    middleware = custom_api.get_namespaced_custom_object(
        group="traefik.io",
        version="v1alpha1",
        namespace=test_namespace,
        plural="middlewares",
        name=STRIPPREFIX_MIDDLEWARE,
    )
    assert middleware is not None

    # Verify ingresses were created
    networking_v1 = client.NetworkingV1Api()
    ingresses = networking_v1.list_namespaced_ingress(test_namespace)
    ingress_names = [i.metadata.name for i in ingresses.items]
    assert f"{test_namespace}-frontend-ingress" in ingress_names
    assert f"{test_namespace}-backend-ingress" in ingress_names


def test_full_workflow_delete_environment(k8s_client, test_namespace):
    """Test complete delete_environment workflow."""
    # Create resources first
    k8s_client.create_namespace(test_namespace)
    k8s_client.create_deployment(
        name="test-app",
        namespace=test_namespace,
        image="nginx:latest",
        port=80,
        template_dir=DEFAULT_TEMPLATE_DIR,
    )
    k8s_client.create_service(
        name="test-app",
        namespace=test_namespace,
        port=80,
        target_port=80,
        template_dir=DEFAULT_TEMPLATE_DIR,
    )

    # Verify resources exist
    assert k8s_client.namespace_exists(test_namespace)

    # Use delete_environment from main.py
    success = delete_environment(k8s=k8s_client, namespace=test_namespace)

    assert success, "delete_environment should return True"

    # Wait for deletion
    deleted = wait_for_namespace_deletion(
        k8s_client, test_namespace, max_wait=MAX_WAIT_FOR_DELETION
    )
    assert deleted, "Namespace should be deleted within timeout"

    # Verify namespace is gone
    assert not k8s_client.namespace_exists(test_namespace)

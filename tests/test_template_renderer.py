"""
Tests for template_renderer.py
"""

import pytest

from automation.constants import (
    DEPLOYMENT_TEMPLATE,
    INGRESS_TEMPLATE,
    MIDDLEWARE_TEMPLATE,
    SERVICE_TEMPLATE,
    STRIPPREFIX_MIDDLEWARE,
)
from automation.exceptions import TemplateError
from automation.template_renderer import render_template


def test_render_deployment_template_with_valid_data(template_dir):
    """Test rendering deployment template with valid data."""
    data = {
        "name": "test-app",
        "namespace": "test-namespace",
        "image": "nginx:latest",
        "port": 80,
        "env_vars": None,
    }

    result = render_template(DEPLOYMENT_TEMPLATE, data, template_dir)

    assert "name: test-app" in result
    assert "namespace: test-namespace" in result
    assert "image: nginx:latest" in result
    assert "containerPort: 80" in result

    assert "apiVersion: apps/v1" in result
    assert "kind: Deployment" in result

    assert "env:" not in result


def test_render_deployment_with_env_vars(template_dir):
    """Test rendering deployment template with environment variables."""
    data = {
        "name": "test-database",
        "namespace": "test-namespace",
        "image": "postgres:15",
        "port": 5432,
        "env_vars": {
            "POSTGRES_PASSWORD": "secret",
        },
    }

    result = render_template(DEPLOYMENT_TEMPLATE, data, template_dir)

    assert "name: test-database" in result
    assert "namespace: test-namespace" in result
    assert "image: postgres:15" in result
    assert "containerPort: 5432" in result

    assert "apiVersion: apps/v1" in result
    assert "kind: Deployment" in result

    assert "env:" in result
    assert "name: POSTGRES_PASSWORD" in result
    assert 'value: "secret"' in result


def test_render_service_with_valid_data(template_dir):
    """Test rendering service template with valid data."""
    data = {"name": "test-service", "namespace": "test-namespace", "port": 30, "target_port": 80}

    result = render_template(SERVICE_TEMPLATE, data, template_dir)

    assert "name: test-service" in result
    assert "namespace: test-namespace" in result
    assert "port: 30" in result
    assert "targetPort: 80" in result

    assert "apiVersion: v1" in result
    assert "kind: Service" in result


def test_render_template_with_missing_file(template_dir):
    """Test handling of missing template file."""
    data = {
        "name": "test-app",
        "namespace": "test-namespace",
        "image": "nginx:latest",
        "port": 80,
        "env_vars": None,
    }

    with pytest.raises(TemplateError, match="Template not found"):
        render_template("missing.yaml.j2", data, template_dir)


def test_render_template_with_missing_variable(template_dir):
    """Test handling of missing required template variable."""
    data = {"namespace": "test-namespace", "image": "nginx:latest", "port": 80, "env_vars": None}

    with pytest.raises(TemplateError, match="Missing required variable"):
        render_template(DEPLOYMENT_TEMPLATE, data, template_dir)


def test_render_middleware_template(template_dir):
    """Test rendering middleware template with valid data."""
    data = {"name": STRIPPREFIX_MIDDLEWARE, "namespace": "pr-123", "prefixes": ["/pr-123", "/api"]}

    result = render_template(MIDDLEWARE_TEMPLATE, data, template_dir)

    assert f"name: {STRIPPREFIX_MIDDLEWARE}" in result
    assert "namespace: pr-123" in result
    assert "apiVersion: traefik.io/v1alpha1" in result
    assert "kind: Middleware" in result
    assert "stripPrefix:" in result
    assert "- /pr-123" in result
    assert "- /api" in result


def test_render_middleware_template_single_prefix(template_dir):
    """Test rendering middleware template with single prefix."""
    data = {"name": STRIPPREFIX_MIDDLEWARE, "namespace": "pr-999", "prefixes": ["/pr-999"]}

    result = render_template(MIDDLEWARE_TEMPLATE, data, template_dir)

    assert "- /pr-999" in result
    assert result.count("- /pr-") == 1


def test_render_ingress_template(template_dir):
    """Test rendering ingress template with valid data."""
    data = {
        "name": "test-ingress",
        "namespace": "pr-123",
        "path": "/pr-123",
        "service_name": "frontend",
        "service_port": 80,
        "middleware_name": STRIPPREFIX_MIDDLEWARE,
    }

    result = render_template(INGRESS_TEMPLATE, data, template_dir)

    assert "name: test-ingress" in result
    assert "namespace: pr-123" in result
    assert "apiVersion: networking.k8s.io/v1" in result
    assert "kind: Ingress" in result

    assert "traefik.ingress.kubernetes.io/router.entrypoints: web" in result
    assert (
        f"traefik.ingress.kubernetes.io/router.middlewares: pr-123-{STRIPPREFIX_MIDDLEWARE}@kubernetescrd"
        in result
    )

    assert "path: /pr-123" in result
    assert "pathType: Prefix" in result
    assert "name: frontend" in result
    assert "number: 80" in result


def test_render_ingress_different_service_port(template_dir):
    """Test rendering ingress template with different service port."""
    data = {
        "name": "backend-ingress",
        "namespace": "pr-456",
        "path": "/pr-456/api",
        "service_name": "backend",
        "service_port": 5000,
        "middleware_name": STRIPPREFIX_MIDDLEWARE,
    }

    result = render_template(INGRESS_TEMPLATE, data, template_dir)

    assert "name: backend-ingress" in result
    assert "path: /pr-456/api" in result
    assert "name: backend" in result
    assert "number: 5000" in result
    assert f"pr-456-{STRIPPREFIX_MIDDLEWARE}@kubernetescrd" in result

"""
Tests for template_renderer.py
"""
import pytest
from automation.template_renderer import render_template

TEMPLATE_DIR = "tests/fixtures/template_renderer/"

def test_render_deployment_template_with_valid_data():
    """Test rendering deployment template with valid data."""
    data = {
        'name': 'test-app',
        'namespace': 'test-namespace',
        'image': 'nginx:latest',
        'port': 80,
        'env_vars': None
    }

    result = render_template('deployment.yaml.j2', data, TEMPLATE_DIR)

    assert result is not None

    assert 'name: test-app' in result
    assert 'namespace: test-namespace' in result
    assert 'image: nginx:latest' in result
    assert 'containerPort: 80' in result

    assert 'apiVersion: apps/v1' in result
    assert 'kind: Deployment' in result

    assert 'env:' not in result

def test_render_deployment_with_env_vars():
    """Test rendering deployment template with environment variables."""
    data = {
        'name': 'test-database',
        'namespace': 'test-namespace',
        'image': 'postgres:15',
        'port': 5432,
        'env_vars': {
            'POSTGRES_PASSWORD': 'secret',
        }
    }

    result = render_template('deployment.yaml.j2', data, TEMPLATE_DIR)

    assert result is not None

    assert 'name: test-database' in result
    assert 'namespace: test-namespace' in result
    assert 'image: postgres:15' in result
    assert 'containerPort: 5432' in result

    assert 'apiVersion: apps/v1' in result
    assert 'kind: Deployment' in result

    assert 'env:' in result
    assert 'name: POSTGRES_PASSWORD' in result
    assert 'value: "secret"' in result

def test_render_service_with_valid_data():
    """Test rendering service template with valid data."""
    data = {
        'name': 'test-service',
        'namespace': 'test-namespace',
        'port': 30,
        'target_port': 80
    }

    result = render_template('service.yaml.j2', data, TEMPLATE_DIR)

    assert result is not None

    assert 'name: test-service' in result
    assert 'namespace: test-namespace' in result
    assert 'port: 30' in result
    assert 'targetPort: 80' in result

    assert 'apiVersion: v1' in result
    assert 'kind: Service' in result

def test_render_template_with_missing_file():
    """Test handling of missing template file."""
    data = {
        'name': 'test-app',
        'namespace': 'test-namespace',
        'image': 'nginx:latest',
        'port': 80,
        'env_vars': None
    }

    result = render_template('missing.yaml.j2', data, TEMPLATE_DIR)

    assert result is None

def test_render_template_with_missing_variable():
    """Test handling of missing required template variable."""
    data = {
        'namespace': 'test-namespace',
        'image': 'nginx:latest',
        'port': 80,
        'env_vars': None
    }

    result = render_template('deployment.yaml.j2', data, TEMPLATE_DIR)

    assert result is None

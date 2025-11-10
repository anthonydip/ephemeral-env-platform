"""
Ephemeral Environment Platform

Automated ephemeral preview environments for pull requests using Kubernetes.
"""

__version__ = "0.1.0"

from automation.config_parser import load_config
from automation.exceptions import (
    ConfigError,
    EphemeralEnvError,
    GitHubError,
    KubernetesError,
    ResourceAlreadyExistsError,
    ResourceNotFoundError,
    TemplateError,
    ValidationError,
)
from automation.k8s_client import KubernetesClient
from automation.template_renderer import render_template

__all__ = [
    "KubernetesClient",
    "load_config",
    "render_template",
    "EphemeralEnvError",
    "ConfigError",
    "ValidationError",
    "TemplateError",
    "GitHubError",
    "KubernetesError",
    "ResourceAlreadyExistsError",
    "ResourceNotFoundError",
]

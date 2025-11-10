"""
Custom exceptions for ephemeral environment platform.

Provides domain-specific exceptions for better error handling and clarity.
All exceptions inherit from EphemeralEnvError for easy catching of all
platform-specific errors.
"""


class EphemeralEnvError(Exception):
    """
    Base exception for all ephemeral environment platform errors.

    All custom exceptions in this module inherit from this base class,
    allowing calling code to catch all platform-specific errors with a
    single except clause if needed.

    Example:
        try:
            create_environment(...)
        except EphemeralEnvError as e:
            logger.error(f"Platform error: {e}")
    """

    pass


class ConfigError(EphemeralEnvError):
    """
    Configuration-related errors.

    Raised when there are issues with configuration files, such as:
    - File not found
    - Invalid YAML syntax
    - Missing required fields
    - Invalid field values
    """

    pass


class ValidationError(EphemeralEnvError):
    """
    Validation errors for user input or resource specifications.

    Raised when validation fails for:
    - Kubernetes resource names
    - Port numbers
    - Docker image names
    - Other input validation
    """

    pass


class TemplateError(EphemeralEnvError):
    """
    Template rendering errors.

    Raised when there are issues with Jinja2 templates:
    - Template file not found
    - Template syntax errors
    - Missing template variables
    - Rendering failures
    """

    pass


class GitHubError(EphemeralEnvError):
    """
    GitHub API interaction errors.

    Raised when GitHub API operations fail:
    - Authentication failures
    - API rate limits
    - Comment posting failures
    - Repository access failures
    """

    pass


class KubernetesError(EphemeralEnvError):
    """
    Base exception for Kubernetes API errors.

    Raised when Kubernetes API operations fail. More specific Kubernetes
    errors inherit from this class.
    """

    pass


class ResourceAlreadyExistsError(KubernetesError):
    """
    Kubernetes resource already exists (409 Conflict).

    Raised when attempting to create a resource that already exists.
    This is typically a recoverable error where the operation can
    proceed with an update instead.
    """

    pass


class ResourceNotFoundError(KubernetesError):
    """
    Kubernetes resource not found (404 Not Found).

    Raised when attempting to access or modify a resource that doesn't exist.
    """

    pass

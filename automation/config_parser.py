"""
Configuration file parser for ephemeral environment platform.

Loads and validates YAML configuration files that define services
to be deployed in preview environments.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from yaml import YAMLError, safe_load

from automation.exceptions import ConfigError
from automation.logger import get_logger

logger = get_logger(__name__)


def load_config(config_path: str) -> dict[str, Any]:
    """
    Load and parse YAML configuration file.

    Args:
        config_path: Path to the .ephemeral-config.yml file

    Returns:
        dict: Parsed configuration

    Raises:
        ConfigError: If file not found, invalid YAML, or missing required fields
    """
    path = Path(config_path)

    if not path.is_file():
        raise ConfigError(f"Config file not found: {config_path}")

    logger.debug(f"Loading config from {config_path}")

    try:
        with open(config_path) as file:
            config = safe_load(file)
    except YAMLError as e:
        raise ConfigError(f"Invalid YAML syntax in config file: {e}") from e
    except OSError as e:
        raise ConfigError(f"Could not read config file {config_path}: {e}") from e

    if not config:
        raise ConfigError(f"Config file is empty: {config_path}")

    if "services" not in config:
        raise ConfigError("Config missing required field: 'services'")

    if not isinstance(config["services"], list):
        raise ConfigError("Config 'services' must be a list")

    if len(config["services"]) == 0:
        raise ConfigError("Config 'services' list is empty")

    for i, service in enumerate(config["services"]):
        _validate_service(service, i, config_path)

    logger.info(
        "Successfully loaded config",
        extra={"config_path": config_path, "service_count": len(config["services"])},
    )

    return config


def _validate_service(service: dict, index: int, config_path: str) -> None:
    """
    Validate a single service configuration.

    Args:
        service: Service configuration dict
        index: Index of service in services list
        config_path: Path to config file (for error messages)

    Raises:
        ConfigError: If service is missing required fields
    """
    if not isinstance(service, dict):
        raise ConfigError(
            f"Service at index {index} must be a dictionary, got {type(service).__name__}"
        )

    required_fields = ["name", "image", "port"]

    for field in required_fields:
        if field not in service:
            service_name = service.get("name", f"service at index {index}")
            raise ConfigError(f"Service '{service_name}' missing required field: '{field}'")

    if not isinstance(service["name"], str):
        raise ConfigError(f"Service 'name' must be a string, got {type(service['name']).__name__}")

    if not isinstance(service["image"], str):
        raise ConfigError(
            f"Service '{service['name']}' 'image' must be a string, get {type(service['image']).__name__}"
        )

    if not isinstance(service["port"], int):
        raise ConfigError(
            f"Service '{service['name']}' 'port' must be an integer, got {type(service['port']).__name__}"
        )

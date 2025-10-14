"""
Configuration file parser for ephemeral environment platform.

Loads and validates YAML configuration files that define services
to be deployed in preview environments.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from yaml import YAMLError, safe_load

from automation.logger import get_logger

logger = get_logger(__name__)


def load_config(config_path: str) -> dict[str, Any] | None:
    """
    Load and parse YAML configuration file.

    Args:
        config_path: Path to the .ephemeral-config.yml file

    Returns:
        dict: Parsed configuration, or None if loading failed
    """
    path = Path(config_path)

    if not path.is_file():
        logger.error("Config file not found", extra={"config_path": config_path})
        return None

    logger.debug(f"Loading config from {config_path}")

    try:
        with open(config_path) as file:
            config = safe_load(file)

        # Validate structure
        if "services" not in config:
            logger.error("Config missing 'services' key", extra={"config_path": config_path})
            return None

        # Validate each service
        for i, service in enumerate(config["services"]):
            if "name" not in service:
                logger.error(
                    "Service missing 'name' field",
                    extra={"config_path": config_path, "service_index": i},
                )
                return None
            if "image" not in service:
                logger.error(
                    "Service missing 'image' field",
                    extra={
                        "config_path": config_path,
                        "service_index": i,
                        "service_name": service.get("name"),
                    },
                )
                return None
            if "port" not in service:
                logger.error(
                    "Service missing 'port' field",
                    extra={
                        "config_path": config_path,
                        "service_index": i,
                        "service_name": service.get("name"),
                    },
                )
                return None

        logger.info(
            "Successfully loaded config",
            extra={"config_path": config_path, "service_count": len(config["services"])},
        )
        return config

    except YAMLError as e:
        logger.error(
            "Invalid YAML syntax in config file",
            extra={"config_path": config_path, "error": str(e)},
        )
        return None
    except OSError as e:
        logger.error(
            "Could not read config file", extra={"config_path": config_path, "error": str(e)}
        )
        return None

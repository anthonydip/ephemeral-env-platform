from __future__ import annotations

from pathlib import Path
from typing import Any

from yaml import YAMLError, safe_load


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
        print(f"Error: Config file '{config_path}' does not exist")
        return None

    try:
        with open(config_path) as file:
            config = safe_load(file)

        # Validate structure
        if "services" not in config:
            print("Config must have 'services' key")
            return None

        # Validate each service
        for i, service in enumerate(config["services"]):
            if "name" not in service:
                print(f"Service at index {i} must have a 'name'")
                return None
            if "image" not in service:
                print(f"Service at index {i} must have an 'image'")
                return None
            if "port" not in service:
                print(f"Service at index {i} must have a 'port'")
                return None

        print(f"Successfully loaded config from {config_path}")
        return config

    except YAMLError:
        print(f"Invalid YAML syntax in '{config_path}'")
        return None
    except OSError:
        print(f"Could not read config file '{config_path}'")
        return None

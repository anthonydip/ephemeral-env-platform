"""
Tests for config_parser.py
"""

import pytest

from automation.config_parser import load_config
from automation.exceptions import ConfigError


def test_load_config_with_env_vars():
    """Test that config with env loads successfully."""
    config = load_config("tests/fixtures/config_parser/config_with_env.yaml")

    assert "services" in config
    db_service = next(s for s in config["services"] if s["name"] == "database")
    assert "env" in db_service
    assert db_service["env"]["POSTGRES_PASSWORD"] == "mysecretpassword"
    assert db_service["env"]["POSTGRES_USER"] == "myuser"
    assert db_service["env"]["POSTGRES_DB"] == "mydb"


def test_load_config_without_env_vars():
    """Test that config without env loads successfully."""
    config = load_config("tests/fixtures/config_parser/config_without_env.yaml")

    assert "services" in config
    assert len(config["services"]) > 0


def test_load_nonexistent_file():
    """Test that loading a missing file returns None."""
    with pytest.raises(ConfigError, match="Config file not found"):
        load_config("tests/fixtures/config_parser/nonexistent.yaml")


def test_load_invalid_yaml_syntax():
    """Test that malformed YAML is handled gracefully."""
    with pytest.raises(ConfigError, match="Invalid YAML syntax"):
        load_config("tests/fixtures/config_parser/invalid_yaml.yaml")


def test_load_config_without_services_key():
    """Test that service without 'services' key is rejected."""
    with pytest.raises(ConfigError, match="missing required field: 'services'"):
        load_config("tests/fixtures/config_parser/no_service_key.yaml")


def test_load_config_without_name():
    """Test that service without 'name' field is rejected."""
    with pytest.raises(ConfigError, match="missing required field: 'name'"):
        load_config("tests/fixtures/config_parser/service_missing_name.yaml")


def test_load_config_without_image():
    """Test that service without 'image' field is rejected."""
    with pytest.raises(ConfigError, match="missing required field: 'image'"):
        load_config("tests/fixtures/config_parser/service_missing_image.yaml")


def test_load_config_without_port():
    """Test that service without 'port' field is rejected."""
    with pytest.raises(ConfigError, match="missing required field: 'port'"):
        load_config("tests/fixtures/config_parser/service_missing_port.yaml")

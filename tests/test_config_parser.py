"""
Tests for config_parser.py
"""

from automation.config_parser import load_config


def test_load_config_with_env_vars():
    """Test that config with env loads successfully."""
    config = load_config("tests/fixtures/config_parser/config_with_env.yaml")

    assert config is not None
    assert "services" in config

    db_service = next(s for s in config["services"] if s["name"] == "database")

    assert "env" in db_service
    assert db_service["env"]["POSTGRES_PASSWORD"] == "mysecretpassword"
    assert db_service["env"]["POSTGRES_USER"] == "myuser"
    assert db_service["env"]["POSTGRES_DB"] == "mydb"


def test_load_config_without_env_vars():
    """Test that config without env loads successfully."""
    config = load_config("tests/fixtures/config_parser/config_without_env.yaml")

    assert config is not None
    assert "services" in config
    assert len(config["services"]) > 0


def test_load_nonexistent_file():
    """Test that loading a missing file returns None."""
    config = load_config("tests/fixtures/config_parser/nonexistent.yaml")
    assert config is None


def test_load_invalid_yaml_syntax():
    """Test that malformed YAML is handled gracefully."""
    config = load_config("tests/fixtures/config_parser/invalid_yaml.yaml")
    assert config is None


def test_load_config_without_services_key():
    """Test that service without 'services' key is rejected."""
    config = load_config("tests/fixtures/config_parser/missing_service.yaml")
    assert config is None


def test_load_config_without_name():
    """Test that service without 'name' field is rejected."""
    config = load_config("tests/fixtures/config_parser/service_missing_name.yaml")
    assert config is None


def test_load_config_without_image():
    """Test that service without 'image' field is rejected."""
    config = load_config("tests/fixtures/config_parser/service_missing_image.yaml")
    assert config is None


def test_load_config_without_port():
    """Test that service without 'port' field is rejected."""
    config = load_config("tests/fixtures/config_parser/service_missing_port.yaml")
    assert config is None

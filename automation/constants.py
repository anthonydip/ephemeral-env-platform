"""
Constants for ephemeral environment platform.

Centralized location for all magic strings, numbers, and configuration values.
"""

# ============================================================================
# Namespace Configuration
# ============================================================================

# Prefix for ephemeral environment namespaces (e.g. 'pr-123')
NAMESPACE_PREFIX = "pr-"

# ============================================================================
# Default Paths
# ============================================================================

# Default path for ephemeral environment configuration file
DEFAULT_CONFIG_PATH = ".ephemeral-config.yaml"

# Default directory for Jinja2 templates
DEFAULT_TEMPLATE_DIR = "automation/templates/"

# Default log file path
DEFAULT_LOG_FILE = "logs/ephemeral-env.log"

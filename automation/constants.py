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
# Kubernetes Validation Limits
# ============================================================================

# Maximum length for Kubernetes resource names (RFC 1123)
MAX_K8S_NAME_LENGTH = 63

# Minimum valid port number
MIN_PORT = 1

# Maximum valid port number
MAX_PORT = 65535

# Recommended maximum image length for Docker image references
MAX_IMAGE_LENGTH = 255

# ============================================================================
# Traefik Configuration
# ============================================================================

# Name of the StripPrefix middleware for path routing
STRIPPREFIX_MIDDLEWARE = "stripprefix"

# ============================================================================
# Default Paths
# ============================================================================

# Default path for ephemeral environment configuration file
DEFAULT_CONFIG_PATH = ".ephemeral-config.yaml"

# Default directory for Jinja2 templates
DEFAULT_TEMPLATE_DIR = "automation/templates/"

# Default log file path
DEFAULT_LOG_FILE = "logs/ephemeral-env.log"

# ============================================================================
# Port Configuration
# ============================================================================

# Offset added to service ports for kubectl port-forward suggestions
PORT_FORWARD_OFFSET = 1000

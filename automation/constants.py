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
# Configuration Parsing
# ============================================================================

# Required fields for service configuration
REQUIRED_SERVICE_FIELDS = ["name", "image", "port"]

# ============================================================================
# Jinja2 Template Files
# ============================================================================

# Deployment template file name
DEPLOYMENT_TEMPLATE = "deployment.yaml.j2"

# Service template file name
SERVICE_TEMPLATE = "service.yaml.j2"

# Middleware template file name
MIDDLEWARE_TEMPLATE = "middleware.yaml.j2"

# Ingress template file name
INGRESS_TEMPLATE = "ingress.yaml.j2"

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
# GitHub Configuration
# ============================================================================

# Marker to identify preview environment comments
PREVIEW_READY_MARKER = "🚀 **Preview Environment Ready!**"

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

# ============================================================================
# Environment Variable Names
# ============================================================================

# GitHub access token
GITHUB_TOKEN = "GITHUB_TOKEN"

# GitHub repository (format owner/repo)
GITHUB_REPO = "GITHUB_REPO"

# Logging level
LOG_LEVEL = "LOG_LEVEL"

# Log file path
LOG_FILE = "LOG_FILE"

# EC2 public IP
EC2_PUBLIC_IP = "EC2_PUBLIC_IP"

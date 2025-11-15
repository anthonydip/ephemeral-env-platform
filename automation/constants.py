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
# Default Paths and Variables
# ============================================================================

# Default path for ephemeral environment configuration file
DEFAULT_CONFIG_PATH = ".ephemeral-config.yaml"

# Default directory for Jinja2 templates
DEFAULT_TEMPLATE_DIR = "automation/templates/"

# Default log file path
DEFAULT_LOG_FILE = "logs/ephemeral-env.log"

# Default log level
DEFAULT_LOG_LEVEL = "INFO"

# Default log output format
DEFAULT_LOG_FORMAT = "text"

# ============================================================================
# Port Configuration
# ============================================================================

# Offset added to service ports for kubectl port-forward suggestions
PORT_FORWARD_OFFSET = 1000

# ============================================================================
# Logger Configuration
# ============================================================================

# Reserved LogRecord attributes for extra fields
RESERVED_ATTRS = {
    "name",
    "msg",
    "args",
    "created",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "module",
    "msecs",
    "message",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "thread",
    "threadName",
    "exc_info",
    "exc_text",
    "taskName",
}

# Fields to exclude from extra_fields extraction
EXCLUDED_EXTRA_FIELDS = {"operation_id", "extra_fields"}

# Date format for JSON formatter
JSON_DATEFMT = "%Y-%m-%dT%H:%M:%S"

# Console output format for structured formatter
STRUCT_CONSOLE_FMT = "[%(operation_id)s] | %(levelname)-8s | %(message)s"

# File output format for structured formatter
STRUCT_FILE_FMT = "%(asctime)s | [%(operation_id)s] | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d | %(message)s"

# Date format for structured formatter
STRUCT_DATEFMT = "%Y-%m-%d %H:%M:%S"

# Console output format for text formatter
TEXT_CONSOLE_FMT = "[%(operation_id)s] | %(levelname)-8s | %(message)s"

# File output format for text formatter
TEXT_FILE_FMT = "%(asctime)s | [%(operation_id)s] | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d | %(message)s"

# Date format for text formatter
TEXT_DATEFMT = "%Y-%m-%d %H:%M:%S"

# Maximum size of a log file before rotation
LOG_MAX_BYTES = 10 * 1024 * 1024  # 10 MB

# Number of rotated log files to keep
LOG_BACKUP_COUNT = 5

# ============================================================================
# Environment Variable Names
# ============================================================================

# GitHub access token
GITHUB_TOKEN = "GITHUB_TOKEN"

# GitHub repository (format owner/repo)
GITHUB_REPO = "GITHUB_REPO"

# GitHub Actions run ID
GITHUB_RUN_ID = "GITHUB_RUN_ID"

# Logging level
LOG_LEVEL = "LOG_LEVEL"

# Log file path
LOG_FILE = "LOG_FILE"

# Ingress host public IP
HOST_PUBLIC_IP = "HOST_PUBLIC_IP"

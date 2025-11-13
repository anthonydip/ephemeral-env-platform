"""
Jinja2 template renderer for Kubernetes manifests.

Renders YAML templates for deployments, services, and other Kubernetes
resources with dynamic data from configuration files.
"""

from __future__ import annotations

import time
from typing import Any

from jinja2 import (
    Environment,
    FileSystemLoader,
    StrictUndefined,
    TemplateNotFound,
    TemplateSyntaxError,
    UndefinedError,
)

from automation.constants import DEFAULT_TEMPLATE_DIR
from automation.exceptions import TemplateError
from automation.logger import get_logger

logger = get_logger(__name__)


def render_template(
    template_name: str, data: dict[str, Any], template_dir: str = DEFAULT_TEMPLATE_DIR
) -> str:
    """
    Render Jinja2 template with provided data.

    Args:
        template_name: Name of template file (e.g., 'deployment.yaml.j2')
        data: Dictionary containing data from parsed configuration file
        template_dir: Directory containing templates (default: automation/templates/)

    Returns:
        str: Rendered YAML content

    Raises:
        TemplateError: If template not found, syntax error, or rendering fails
    """
    start_time = time.perf_counter()

    logger.debug(
        f"Rendering template: {template_name}",
        extra={"template": template_name, "template_dir": template_dir},
    )

    try:
        environment = Environment(loader=FileSystemLoader(template_dir), undefined=StrictUndefined)
        template = environment.get_template(template_name)
        rendered = template.render(data)

        duration = time.perf_counter() - start_time

        logger.info(
            "Successfully rendered template",
            extra={
                "template": template_name,
                "size_bytes": len(rendered),
                "duration_seconds": round(duration, 3),
            },
        )
        return rendered

    except TemplateNotFound as e:
        raise TemplateError(f"Template not found: {template_name} in {template_dir}") from e

    except TemplateSyntaxError as e:
        raise TemplateError(
            f"Invalid syntax in template {template_name} at line {e.lineno}: {e.message}"
        ) from e

    except UndefinedError as e:
        raise TemplateError(f"Missing required variable in template {template_name}: {e}") from e

    except Exception as e:
        raise TemplateError(f"Failed to render template {template_name}: {e}") from e

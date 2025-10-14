"""
Jinja2 template renderer for Kubernetes manifests.

Renders YAML templates for deployments, services, and other Kubernetes
resources with dynamic data from configuration files.
"""

from __future__ import annotations

from typing import Any

from jinja2 import (
    Environment,
    FileSystemLoader,
    StrictUndefined,
    TemplateNotFound,
    TemplateSyntaxError,
    UndefinedError,
)

from automation.logger import get_logger

logger = get_logger(__name__)


def render_template(
    template_name: str, data: dict[str, Any], template_dir: str = "automation/templates/"
) -> str | None:
    """
    Render Jinja2 template with provided data.

    Args:
        template_name: Name of template file (e.g., 'deployment.yaml.j2')
        data: Dictionary containing data from parsed configuration file
        template_dir: Directory containing templates (default: automation/templates/)

    Returns:
        str: Rendered YAML content, or None if rendering failed
    """
    logger.debug(
        f"Rendering template: {template_name}",
        extra={"template": template_name, "template_dir": template_dir},
    )

    try:
        environment = Environment(loader=FileSystemLoader(template_dir), undefined=StrictUndefined)
        template = environment.get_template(template_name)
        rendered = template.render(data)

        logger.info(
            "Successfully rendered template",
            extra={"template": template_name, "size": len(rendered)},
        )
        return rendered

    except TemplateNotFound:
        logger.error(
            "Template not found", extra={"template": template_name, "template_dir": template_dir}
        )
        return None

    except TemplateSyntaxError as e:
        logger.error(
            "Invalid template syntax",
            extra={"template": template_name, "line": e.lineno, "error": e.message},
        )
        return None

    except UndefinedError as e:
        logger.error(
            "Missing required variable in template",
            extra={"template": template_name, "error": str(e)},
        )
        return None

    except Exception as e:
        logger.error(
            "Unexpected error rendering template",
            extra={"template": template_name, "error": str(e), "error_type": type(e)},
        )
        return None

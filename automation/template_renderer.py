from jinja2 import Environment, FileSystemLoader, TemplateNotFound, TemplateSyntaxError, UndefinedError, StrictUndefined

def render_template(template_name, data, template_dir="templates/"):
    """
    Render Jinja2 template with provided data.

    Args:
        template_name: Name of template file (e.g., 'deployment.yaml.j2')
        data: Dictionary containing data from parsed configuration file
        template_dir: Directory containing templates (default: templates/)

    Returns:
        str: Rendered YAML content, or None if rendering failed
    """
    try:
        environment = Environment(loader=FileSystemLoader(template_dir), undefined=StrictUndefined)
        template = environment.get_template(template_name)
        return template.render(data)
    
    except TemplateNotFound:
        print(f"Template '{template_name}' not found in {template_dir}")
        return None

    except TemplateSyntaxError as e:
        print(f"Invalid template syntax in '{template_name}'")
        return None

    except UndefinedError as e:
        print(f"Missing required variable in template '{template_name}'")
        return None

    except Exception as e:
        print(f"Unexpected error rendering template '{template_name}'")
        print(f"Details: {e}")
        return None

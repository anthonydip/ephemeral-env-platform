from jinja2 import Environment, FileSystemLoader, TemplateNotFound, TemplateSyntaxError, UndefinedError

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
        environment = Environment(loader=FileSystemLoader(template_dir))
        template = environment.get_template(template_name)
        rendered_yaml = template.render(data)
        return rendered_yaml
    
    except TemplateNotFound:
        print(f"Template '{template_path}' not found in templates/")
        return None

    except TemplateSyntaxError as e:
        print(f"Invalid template syntax in '{template_path}'")
        return None

    except UndefinedError as e:
        print(f"Missing required variable in template '{template_path}'")
        return None

    except Exception as e:
        print(f"Unexpected error rendering template '{template_path}'")
        print(f"Details: {e}")
        return None

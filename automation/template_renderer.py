from jinja2 import Environment, FileSystemLoader, TemplateNotFound, TemplateSyntaxError, UndefinedError

def render_template(template_path, data):
    """
    Render Jinja2 template with provided data.

    Args:
        template_path: Path to the Jinja2 template file
        data: Dictionary containing data from parsed configuration file

    Returns:
        str: Rendered YAML content, or None if rendering failed
    """
    try:
        environment = Environment(loader=FileSystemLoader("templates/"))
        template = environment.get_template(template_path)
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

from django import template

register = template.Library()


@register.filter
def split_commas(value):
    """Split a comma-separated string into a list of stripped strings."""
    if not value:
        return []
    return [g.strip() for g in value.split(',') if g.strip()]


@register.filter
def display_name(user, viewer):
    """
    Display user name based on viewer's authentication status.
    If viewer is authenticated: return full name (or username if no first/last name)
    If viewer is not authenticated: return first name + first letter of last name (or username if no first name)

    Usage: {{ user|display_name:request.user }}
    """
    if not user:
        return ""

    # Safely get first_name and last_name (handle None or empty strings)
    first_name = (user.first_name or "").strip()
    last_name = (user.last_name or "").strip()

    # Fallback to username if first name is not set
    if not first_name:
        return user.username

    if viewer and viewer.is_authenticated:
        # Show full name to authenticated users
        return f"{first_name} {last_name}" if last_name else first_name
    else:
        # Show abbreviated name to unauthenticated users
        last_initial = last_name[0] if last_name else ""
        return f"{first_name} {last_initial}".strip()

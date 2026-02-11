from django import template

register = template.Library()


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

    # Fallback to username if first name is not set
    if not user.first_name:
        return user.username

    if viewer and viewer.is_authenticated:
        # Show full name to authenticated users
        return f"{user.first_name} {user.last_name}" if user.last_name else user.first_name
    else:
        # Show abbreviated name to unauthenticated users
        last_initial = user.last_name[0] if user.last_name else ""
        return f"{user.first_name} {last_initial}"

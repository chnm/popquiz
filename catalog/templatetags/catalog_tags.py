from django import template
from catalog.models import Category

register = template.Library()


@register.simple_tag
def get_categories():
    """Return all categories ordered by name."""
    return Category.objects.all().order_by('name')

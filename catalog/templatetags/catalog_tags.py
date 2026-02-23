from django import template
from catalog.models import Category

register = template.Library()


@register.simple_tag
def get_categories():
    """Return all non-music categories ordered by name."""
    return Category.objects.exclude(item_label__in=['artist', 'release']).order_by('name')


@register.simple_tag
def get_music_categories():
    """Return music categories (artists, releases) ordered by name."""
    return Category.objects.filter(item_label__in=['artist', 'release']).order_by('name')

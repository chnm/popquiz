from django.db import models
from django.conf import settings


class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    item_label = models.CharField(
        max_length=50,
        default='movie',
        help_text='Singular label for items in this category (e.g. "movie", "show")'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'categories'
        ordering = ['name']

    @property
    def item_label_plural(self):
        """Plural form of item_label, handling irregular plurals like 'series'."""
        label = self.item_label
        if label.endswith(('s', 'x', 'z')) or label.endswith(('ch', 'sh')):
            return label
        return label + 's'

    def __str__(self):
        return self.name


class Item(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='items')
    title = models.CharField(max_length=255)
    year = models.PositiveIntegerField(null=True, blank=True)
    years_running = models.CharField(max_length=20, blank=True)
    director = models.CharField(max_length=255, blank=True)
    genre = models.CharField(max_length=255, blank=True)
    imdb_id = models.CharField(max_length=20, unique=True, null=True, blank=True)
    imdb_url = models.URLField(blank=True)
    image_source_url = models.URLField(blank=True)
    image_local_url = models.URLField(blank=True)
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='items_added'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['title']

    @property
    def image_url(self):
        """Returns the local cached image if available, otherwise the external source URL."""
        return self.image_local_url or self.image_source_url

    @property
    def display_year(self):
        """Returns years_running range for TV series, or debut year for everything else."""
        if self.years_running:
            return self.years_running
        if self.year:
            return str(self.year)
        return ''

    def __str__(self):
        display = self.display_year
        if display:
            return f"{self.title} ({display})"
        return self.title

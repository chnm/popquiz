from django.db import models
from django.conf import settings


class Category(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'categories'
        ordering = ['name']

    def __str__(self):
        return self.name


class Item(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='items')
    title = models.CharField(max_length=255)
    year = models.PositiveIntegerField(null=True, blank=True)
    director = models.CharField(max_length=255, blank=True)
    imdb_id = models.CharField(max_length=20, unique=True, null=True, blank=True)
    imdb_url = models.URLField(blank=True)
    poster_url = models.URLField(blank=True)
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='items_added'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['title']

    def __str__(self):
        if self.year:
            return f"{self.title} ({self.year})"
        return self.title

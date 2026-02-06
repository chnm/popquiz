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
    imdb_id = models.CharField(max_length=20, unique=True, null=True, blank=True)
    imdb_url = models.URLField(blank=True)
    poster_url = models.URLField(blank=True)
    musicbrainz_id = models.CharField(max_length=36, unique=True, null=True, blank=True)
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


class Song(models.Model):
    artist = models.ForeignKey(Item, on_delete=models.CASCADE, related_name='songs')
    title = models.CharField(max_length=255)
    musicbrainz_id = models.CharField(max_length=36, unique=True, null=True, blank=True)
    year = models.PositiveIntegerField(null=True, blank=True)
    album = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['title']

    def __str__(self):
        return f"{self.title} by {self.artist.title}"

    @property
    def upvote_count(self):
        return self.upvotes.count()


class SongUpvote(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='song_upvotes'
    )
    song = models.ForeignKey(Song, on_delete=models.CASCADE, related_name='upvotes')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'song']
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} upvoted {self.song.title}"

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Custom user model for PopQuiz."""

    avatar_url = models.URLField(max_length=500, blank=True, null=True, help_text="Profile picture URL from social provider")

    class Meta:
        ordering = ['username']

    def __str__(self):
        return self.username


class MagicLink(models.Model):
    """A single-use, time-limited login token sent by email."""
    user = models.ForeignKey(
        'User',
        on_delete=models.CASCADE,
        related_name='magic_links',
    )
    token = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used = models.BooleanField(default=False)

    def __str__(self):
        return f"MagicLink for {self.user.username} ({'used' if self.used else 'active'})"

    @property
    def is_valid(self):
        from django.utils import timezone
        return not self.used and self.expires_at > timezone.now()

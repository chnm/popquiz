from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Custom user model for PopQuiz."""

    avatar_url = models.URLField(max_length=500, blank=True, null=True, help_text="Profile picture URL from social provider")

    class Meta:
        ordering = ['username']

    def __str__(self):
        return self.username

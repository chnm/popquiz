from django.db import models
from django.conf import settings


class Rating(models.Model):
    """User ratings for items using a 5-point Likert scale."""

    class Level(models.TextChoices):
        LOVED = 'loved', '🤩 Loved it'
        LIKED = 'liked', '🙂 Liked it'
        OKAY = 'okay', '😐 It was okay'
        DISLIKED = 'disliked', '😕 Disliked it'
        HATED = 'hated', '😡 Hated it'
        NO_RATING = 'no_rating', '⏭️ Not yet rated'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='ratings'
    )
    item = models.ForeignKey(
        'catalog.Item',
        on_delete=models.CASCADE,
        related_name='ratings'
    )
    rating = models.CharField(
        max_length=10,
        choices=Level.choices,
        default=Level.NO_RATING,
        db_column='choice'  # Keep old column name for SQLite compatibility
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['user', 'item']
        db_table = 'votes_vote'  # Keep old table name for backward compatibility

    def __str__(self):
        return f"{self.user.username} - {self.item.title}: {self.rating}"

    def get_numeric_value(self):
        """Convert rating to numeric value for calculations."""
        rating_values = {
            self.Level.LOVED: 2,
            self.Level.LIKED: 1,
            self.Level.OKAY: 0,
            self.Level.DISLIKED: -1,
            self.Level.HATED: -2,
            self.Level.NO_RATING: None,
        }
        return rating_values.get(self.rating)


# Keep old Vote name as alias for backward compatibility during transition
Vote = Rating

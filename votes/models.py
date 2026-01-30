from django.db import models
from django.conf import settings


class Vote(models.Model):
    class Choice(models.TextChoices):
        YES = 'yes', 'Yes'
        NO = 'no', 'No'
        MEH = 'meh', 'Meh'
        NO_ANSWER = 'no_answer', 'No Answer'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='votes'
    )
    item = models.ForeignKey(
        'catalog.Item',
        on_delete=models.CASCADE,
        related_name='votes'
    )
    choice = models.CharField(
        max_length=10,
        choices=Choice.choices,
        default=Choice.NO_ANSWER
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['user', 'item']

    def __str__(self):
        return f"{self.user.username} - {self.item.title}: {self.choice}"

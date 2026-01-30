from django.contrib import admin
from .models import Vote


@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    list_display = ['user', 'item', 'choice', 'updated_at']
    list_filter = ['choice', 'item__category', 'updated_at']
    search_fields = ['user__username', 'item__title']
    raw_id_fields = ['user', 'item']

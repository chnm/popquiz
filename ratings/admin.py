from django.contrib import admin
from .models import Rating


@admin.register(Rating)
class RatingAdmin(admin.ModelAdmin):
    list_display = ('user', 'item', 'rating', 'updated_at')
    list_filter = ('rating', 'updated_at')
    search_fields = ('user__username', 'item__title')
    readonly_fields = ('updated_at',)
    date_hierarchy = 'updated_at'

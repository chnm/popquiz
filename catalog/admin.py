from django.contrib import admin
from .models import Category, Item


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'item_label', 'created_at']
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ['name']
    fields = ['name', 'slug', 'description', 'item_label']


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ['title', 'year', 'imdb_id', 'category', 'added_by', 'created_at']
    list_filter = ['category', 'created_at']
    search_fields = ['title', 'imdb_id']
    raw_id_fields = ['added_by']

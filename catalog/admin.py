from django.contrib import admin
from .models import Category, Item, Song, SongUpvote


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'created_at']
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ['name']


class SongInline(admin.TabularInline):
    model = Song
    extra = 0
    fields = ['title', 'album', 'year', 'musicbrainz_id']


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ['title', 'year', 'imdb_id', 'musicbrainz_id', 'category', 'added_by', 'created_at']
    list_filter = ['category', 'created_at']
    search_fields = ['title', 'imdb_id', 'musicbrainz_id']
    raw_id_fields = ['added_by']
    inlines = [SongInline]


@admin.register(Song)
class SongAdmin(admin.ModelAdmin):
    list_display = ['title', 'artist', 'album', 'year', 'upvote_count', 'created_at']
    list_filter = ['year', 'created_at']
    search_fields = ['title', 'artist__title', 'album']
    raw_id_fields = ['artist']


@admin.register(SongUpvote)
class SongUpvoteAdmin(admin.ModelAdmin):
    list_display = ['user', 'song', 'created_at']
    list_filter = ['created_at']
    search_fields = ['user__username', 'song__title']
    raw_id_fields = ['user', 'song']

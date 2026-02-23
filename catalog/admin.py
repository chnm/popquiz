from django.contrib import admin
from .models import Category, Item, Song, SongUpvote


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'item_label', 'created_at']
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ['name']
    fields = ['name', 'slug', 'description', 'item_label']


class SongInline(admin.TabularInline):
    model = Song
    fk_name = 'artist'
    extra = 0
    fields = ['title', 'album', 'year', 'musicbrainz_id', 'release']
    raw_id_fields = ['release']


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ['title', 'year', 'imdb_id', 'musicbrainz_id', 'category', 'added_by', 'created_at']
    list_filter = ['category', 'created_at']
    search_fields = ['title', 'imdb_id', 'musicbrainz_id']
    raw_id_fields = ['added_by']
    inlines = [SongInline]


@admin.register(Song)
class SongAdmin(admin.ModelAdmin):
    list_display = ['title', 'artist', 'release', 'album', 'year', 'upvote_count', 'created_at']
    list_filter = ['year', 'created_at']
    search_fields = ['title', 'artist__title', 'album']
    raw_id_fields = ['artist', 'release']


@admin.register(SongUpvote)
class SongUpvoteAdmin(admin.ModelAdmin):
    list_display = ['user', 'song', 'created_at']
    list_filter = ['created_at']
    search_fields = ['user__username', 'song__title']
    raw_id_fields = ['user', 'song']

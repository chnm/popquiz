"""
Management command to backfill genre_tags and spotify_url for existing music releases.
"""
from django.core.management.base import BaseCommand
from catalog.models import Item
from catalog.musicbrainz_utils import fetch_release_data


class Command(BaseCommand):
    help = 'Backfill genre_tags and spotify_url for existing music releases from MusicBrainz'

    def handle(self, *args, **options):
        releases = Item.objects.filter(
            category__slug='music-releases',
        ).exclude(musicbrainz_id__isnull=True).exclude(musicbrainz_id='')

        total = releases.count()
        self.stdout.write(f'Found {total} music release(s) to process.')

        updated = 0
        skipped = 0
        failed = 0

        for item in releases:
            already_has = bool(item.genre_tags or item.spotify_url)
            self.stdout.write(f'  Processing: {item.title!r} ({item.musicbrainz_id})')

            data = fetch_release_data(item.musicbrainz_id)
            if not data:
                self.stdout.write(self.style.WARNING(f'    Failed to fetch data'))
                failed += 1
                continue

            new_genre_tags = data.get('genre_tags', '')
            new_spotify_url = data.get('spotify_url', '')

            update_fields = []
            if new_genre_tags and not item.genre_tags:
                item.genre_tags = new_genre_tags
                update_fields.append('genre_tags')
                self.stdout.write(f'    genres: {new_genre_tags}')
            if new_spotify_url and not item.spotify_url:
                item.spotify_url = new_spotify_url
                update_fields.append('spotify_url')
                self.stdout.write(f'    spotify: {new_spotify_url}')

            if update_fields:
                item.save(update_fields=update_fields)
                updated += 1
            else:
                self.stdout.write(f'    nothing new to update')
                skipped += 1

        self.stdout.write(self.style.SUCCESS(
            f'\nDone. Updated: {updated}, Skipped: {skipped}, Failed: {failed}'
        ))

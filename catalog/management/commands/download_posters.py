"""
Management command to download all external poster images to local storage.
Run this once to backfill existing items, then new items cache automatically.
"""
import time

from django.core.management.base import BaseCommand

from catalog.models import Item
from catalog.imdb_utils import download_poster


class Command(BaseCommand):
    help = 'Download poster images from external URLs (IMDB/Amazon) to local storage'

    def handle(self, *args, **options):
        items = Item.objects.exclude(poster_url='').filter(
            poster_url__startswith='http'
        )
        total = items.count()

        if total == 0:
            self.stdout.write('No external poster URLs found — nothing to do.')
            return

        self.stdout.write(f'Downloading posters for {total} items...')

        success = 0
        failed = 0
        skipped = 0

        for i, item in enumerate(items, 1):
            identifier = item.imdb_id or str(item.pk)
            local_url = download_poster(item.poster_url, identifier)

            if local_url:
                item.poster_url = local_url
                item.save(update_fields=['poster_url'])
                success += 1
                self.stdout.write(f'  [{i}/{total}] OK: {item.title}')
            else:
                failed += 1
                self.stdout.write(f'  [{i}/{total}] FAILED: {item.title}')

            time.sleep(0.2)  # Gentle rate limiting

        self.stdout.write(
            f'\nDone: {success} downloaded, {failed} failed, {skipped} skipped'
        )

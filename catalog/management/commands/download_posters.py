"""
Management command to download all external item images to local storage.
Run this once to backfill existing items, then new items cache automatically.
"""
import time

from django.core.management.base import BaseCommand

from catalog.models import Item
from catalog.imdb_utils import download_poster


class Command(BaseCommand):
    help = 'Download item images from external URLs (IMDB/Amazon) to local storage'

    def handle(self, *args, **options):
        # Target items that have a source URL but no local copy yet
        items = Item.objects.exclude(image_source_url='').filter(image_local_url='')
        total = items.count()

        if total == 0:
            self.stdout.write('No items need image downloads — nothing to do.')
            return

        self.stdout.write(f'Downloading images for {total} items...')

        success = 0
        failed = 0

        for i, item in enumerate(items, 1):
            identifier = item.imdb_id or str(item.pk)
            local_url = download_poster(item.image_source_url, identifier)

            if local_url:
                item.image_local_url = local_url
                item.save(update_fields=['image_local_url'])
                success += 1
                self.stdout.write(f'  [{i}/{total}] OK: {item.title}')
            else:
                failed += 1
                self.stdout.write(f'  [{i}/{total}] FAILED: {item.title}')

            time.sleep(0.2)  # Gentle rate limiting

        self.stdout.write(
            f'\nDone: {success} downloaded, {failed} failed'
        )

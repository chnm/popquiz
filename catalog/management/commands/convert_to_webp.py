"""
Management command to convert existing JPG poster images to WebP format.
Deletes the original JPG after successful conversion and updates the database.
"""
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from PIL import Image

from catalog.models import Item


class Command(BaseCommand):
    help = 'Convert existing JPG poster images to WebP and update item records'

    def handle(self, *args, **options):
        media_dir = Path(settings.MEDIA_ROOT) / 'posters'
        jpg_files = sorted(media_dir.glob('*.jpg'))
        total = len(jpg_files)

        if total == 0:
            self.stdout.write('No JPG files found — nothing to do.')
            return

        self.stdout.write(f'Converting {total} JPG files to WebP...')

        success = 0
        failed = 0

        for i, jpg_path in enumerate(jpg_files, 1):
            stem = jpg_path.stem
            webp_path = jpg_path.parent / f'{stem}.webp'
            old_local_url = f'{settings.MEDIA_URL}posters/{stem}.jpg'
            new_local_url = f'{settings.MEDIA_URL}posters/{stem}.webp'

            try:
                with Image.open(jpg_path) as img:
                    if img.mode not in ('RGB', 'L'):
                        img = img.convert('RGB')
                    img.save(webp_path, 'WEBP', quality=85)

                # Update any items pointing at the old JPG path
                updated = Item.objects.filter(image_local_url=old_local_url).update(
                    image_local_url=new_local_url
                )

                # Remove the original JPG
                jpg_path.unlink()

                success += 1
                if i % 100 == 0 or i == total:
                    self.stdout.write(f'  Progress: {i}/{total} (db rows updated this file: {updated})')

            except Exception as e:
                failed += 1
                self.stdout.write(f'  FAILED [{i}/{total}]: {jpg_path.name} — {e}')

        self.stdout.write(f'\nDone: {success} converted, {failed} failed')

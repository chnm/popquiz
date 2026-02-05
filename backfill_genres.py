"""
Script to backfill genre information for existing movies in the database.
Fetches genre data from IMDB for all movies that have an IMDB ID but no genre.
"""
import os
import sys
import django
import time

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'popquiz.settings')
django.setup()

from catalog.models import Item
from catalog.imdb_utils import fetch_movie_data

def print_flush(msg):
    """Print with immediate flush."""
    print(msg)
    sys.stdout.flush()

def backfill_genres():
    """Fetch and update genre information for all movies."""

    # Get all items that need genre information
    items_to_update = Item.objects.filter(
        imdb_id__isnull=False
    ).exclude(
        imdb_id=''
    ).filter(
        genre=''
    )

    total = items_to_update.count()
    print_flush(f"Found {total} movies without genre information")
    print_flush("Starting to fetch genre data from IMDB...")
    print_flush("-" * 60)

    updated = 0
    failed = 0
    skipped = 0

    for i, item in enumerate(items_to_update, 1):
        print_flush(f"[{i}/{total}] Processing: {item.title} ({item.year})")

        if not item.imdb_id:
            print_flush(f"  ⚠️  No IMDB ID, skipping")
            skipped += 1
            continue

        # Fetch movie data from IMDB
        movie_data = fetch_movie_data(item.imdb_id)

        if movie_data and movie_data.get('genre'):
            item.genre = movie_data['genre']
            item.save()
            print_flush(f"  ✓ Updated: Genre = {item.genre}")
            updated += 1
        else:
            print_flush(f"  ✗ Failed to fetch genre information")
            failed += 1

        # Be nice to IMDB - add a small delay between requests
        if i < total:
            time.sleep(0.5)

    print_flush("-" * 60)
    print_flush("\n📊 Summary:")
    print_flush(f"  Total movies processed: {total}")
    print_flush(f"  ✓ Successfully updated: {updated}")
    print_flush(f"  ✗ Failed to fetch: {failed}")
    print_flush(f"  ⚠️  Skipped: {skipped}")
    print_flush(f"\nGenre information has been updated for {updated} movies!")

if __name__ == '__main__':
    try:
        backfill_genres()
    except KeyboardInterrupt:
        print_flush("\n\n⚠️  Script interrupted by user")
        sys.exit(1)
    except Exception as e:
        print_flush(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

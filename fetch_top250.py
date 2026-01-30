"""
Script to fetch IMDB Top 250 movies and add them to the database.
"""
import os
import sys
import django
import re
import requests
from time import sleep

# Setup Django
sys.path.insert(0, '/Users/vibes/Desktop/popquiz')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'popquiz.settings')
django.setup()

from catalog.models import Category, Item
from catalog.imdb_utils import fetch_movie_data, HEADERS
from django.contrib.auth import get_user_model

User = get_user_model()


def fetch_top_250_ids():
    """Fetch the list of IMDB IDs from the Top 250 page."""
    url = "https://www.imdb.com/chart/top/"
    print(f"Fetching {url}...")

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            print(f"Failed to fetch page. Status: {resp.status_code}")
            return []

        html = resp.text

        # Extract all IMDB IDs from the page
        # Looking for patterns like /title/tt0111161/
        imdb_ids = re.findall(r'/title/(tt\d+)/', html)

        # Remove duplicates while preserving order
        seen = set()
        unique_ids = []
        for imdb_id in imdb_ids:
            if imdb_id not in seen:
                seen.add(imdb_id)
                unique_ids.append(imdb_id)

        print(f"Found {len(unique_ids)} unique movie IDs")
        return unique_ids

    except requests.RequestException as e:
        print(f"Error fetching page: {e}")
        return []


def main():
    # Get or create Movies category
    category, created = Category.objects.get_or_create(
        slug='movies',
        defaults={'name': 'Movies', 'description': 'Feature films and cinema'}
    )
    if created:
        print(f"Created category: {category.name}")
    else:
        print(f"Using existing category: {category.name}")

    # Get a system user for added_by field (or create one)
    admin_user = User.objects.filter(is_staff=True).first()
    if not admin_user:
        print("Warning: No admin user found. Items will be added without an added_by user.")

    # Fetch the Top 250 IDs
    imdb_ids = fetch_top_250_ids()

    if not imdb_ids:
        print("No movies found. Exiting.")
        return

    # Process each movie
    added_count = 0
    skipped_count = 0
    error_count = 0

    for i, imdb_id in enumerate(imdb_ids, 1):
        print(f"\n[{i}/{len(imdb_ids)}] Processing {imdb_id}...")

        # Check if movie already exists
        if Item.objects.filter(imdb_id=imdb_id).exists():
            print(f"  ✓ Already in database")
            skipped_count += 1
            continue

        # Fetch movie data
        print(f"  Fetching data from IMDB...")
        movie_data = fetch_movie_data(imdb_id)

        if not movie_data:
            print(f"  ✗ Failed to fetch data")
            error_count += 1
            continue

        # Create the item
        try:
            item = Item.objects.create(
                category=category,
                title=movie_data['title'],
                year=movie_data.get('year'),
                imdb_id=movie_data['imdb_id'],
                imdb_url=movie_data['imdb_url'],
                poster_url=movie_data.get('poster_url', ''),
                added_by=admin_user
            )
            print(f"  ✓ Added: {item.title} ({item.year})")
            added_count += 1

            # Be respectful - add a small delay between requests
            sleep(0.5)

        except Exception as e:
            print(f"  ✗ Error creating item: {e}")
            error_count += 1

    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Total movies processed: {len(imdb_ids)}")
    print(f"Added to database: {added_count}")
    print(f"Already in database: {skipped_count}")
    print(f"Errors: {error_count}")
    print("="*60)


if __name__ == '__main__':
    main()

"""
Script to fetch popular music artists from MusicBrainz and add them to the database.
"""
import os
import sys
import django
from time import sleep

# Setup Django - update path as needed
project_path = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_path)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'popquiz.settings')
django.setup()

from catalog.models import Category, Item, Song
from catalog.musicbrainz_utils import fetch_artist_data
from django.contrib.auth import get_user_model

User = get_user_model()


# Curated list of popular artists across genres
# Format: (musicbrainz_id, artist_name) - name is just for reference
POPULAR_ARTISTS = [
    # Rock/Classic Rock
    ('b10bbbfc-cf9e-42e0-be17-e2c3e1d2600d', 'The Beatles'),
    ('83d91898-7763-47d7-b03b-b92132375c47', 'Pink Floyd'),
    ('cc197bad-dc9c-440d-a5b5-d52ba2e14234', 'The Rolling Stones'),
    ('5b11f4ce-a62d-471e-81fc-a69a8278c7da', 'The Who'),
    ('65f4f0c5-ef9e-490c-aee3-909e7ae6b2ab', 'Metallica'),
    ('9c9f1380-2516-4fc9-a3e6-f9f61941d090', 'Muse'),

    # Pop
    ('b071f9fa-14b0-4217-8e97-eb41da73f598', 'The Weeknd'),
    ('e0140a67-e4d1-4f13-8a01-364355bee46e', 'Billie Eilish'),
    ('f4fdbb4c-e4b7-47a0-b83b-d91bbfcfa387', 'Ariana Grande'),
    ('eeb1195b-f213-4ce1-b28c-8565211f8e43', 'Michael Jackson'),

    # Hip Hop/Rap
    ('381086ea-f511-4aba-bdf9-71c753dc5077', 'Kendrick Lamar'),
    ('164f0d73-1234-4e2c-8743-d77bf2191051', 'Kanye West'),
    ('f82bcf78-5b69-4622-a5ef-73800768d9ac', 'JAY-Z'),
    ('dfdaa4b5-c987-4902-a8d9-34ba92c7e14d', 'Drake'),

    # Electronic/Dance
    ('f6beac20-5dfe-4d1f-ae02-0b0a740aafd6', 'Daft Punk'),
    ('c5c2ea1c-4bde-4f4d-bd0b-47b200bf99d6', 'Avicii'),
    ('8e2a36d4-5f25-443d-9b80-2ec1fc750953', 'Calvin Harris'),

    # Alternative/Indie
    ('a74b1b7f-71a5-4011-9441-d0b5e4122711', 'Radiohead'),
    ('cc0b7089-c08d-4c10-b6b0-873582c17fd6', 'System of a Down'),
    ('8bfac288-ccc5-448d-9573-c33ea2aa5c30', 'Red Hot Chili Peppers'),

    # R&B/Soul
    ('15d0f486-e3b1-4c7b-a16e-ae0993375fb9', 'Beyoncé'),
    ('7e9bd05a-117f-4cce-87bc-e011527a8b18', 'Frank Ocean'),
    ('5441c29d-3602-4898-b1a1-b77fa23b8e50', 'David Bowie'),

    # Country
    ('4f624533-9018-4766-b8c7-b740173e0015', 'Taylor Swift'),
    ('c7e7727c-a86c-47e7-8cb5-af2dd6d0d5fc', 'Johnny Cash'),

    # Jazz/Blues
    ('7e2c6fe4-3289-4740-8e01-f93f8f5c2e8d', 'Miles Davis'),
    ('a3cb23fc-acd3-4ce0-8f36-1e5aa6a18432', 'U2'),
]


def main():
    # Get or create Music Artists category
    category, created = Category.objects.get_or_create(
        slug='music-artists',
        defaults={'name': 'Music Artists', 'description': 'Vote on your favorite music artists'}
    )
    if created:
        print(f"Created category: {category.name}")
    else:
        print(f"Using existing category: {category.name}")

    # Get a system user for added_by field (or create one)
    admin_user = User.objects.filter(is_staff=True).first()
    if not admin_user:
        print("Warning: No admin user found. Items will be added without an added_by user.")

    # Process each artist
    added_count = 0
    skipped_count = 0
    error_count = 0
    total_songs = 0

    print(f"\nFetching {len(POPULAR_ARTISTS)} popular artists from MusicBrainz...")
    print("="*60)

    for i, (mb_id, artist_name) in enumerate(POPULAR_ARTISTS, 1):
        print(f"\n[{i}/{len(POPULAR_ARTISTS)}] Processing {artist_name}...")

        # Check if artist already exists
        if Item.objects.filter(musicbrainz_id=mb_id).exists():
            print(f"  ✓ Already in database")
            skipped_count += 1
            continue

        # Fetch artist data from MusicBrainz
        print(f"  Fetching data from MusicBrainz...")
        artist_data = fetch_artist_data(mb_id, fetch_songs=True, max_songs=100)

        if not artist_data:
            print(f"  ✗ Failed to fetch data")
            error_count += 1
            continue

        # Create the artist item
        try:
            item = Item.objects.create(
                category=category,
                title=artist_data['title'],
                musicbrainz_id=artist_data['musicbrainz_id'],
                poster_url=artist_data.get('poster_url') or '',
                added_by=admin_user
            )
            print(f"  ✓ Added artist: {item.title}")

            # Add songs if any were fetched
            songs_added = 0
            if 'songs' in artist_data and artist_data['songs']:
                for song_data in artist_data['songs']:
                    try:
                        Song.objects.create(
                            artist=item,
                            title=song_data['title'],
                            musicbrainz_id=song_data.get('musicbrainz_id'),
                            year=song_data.get('year'),
                            album=song_data.get('album', ''),
                        )
                        songs_added += 1
                    except Exception as e:
                        # Skip duplicate songs
                        if 'unique constraint' not in str(e).lower():
                            print(f"    Warning: Could not add song '{song_data['title']}': {e}")

                print(f"  ✓ Added {songs_added} songs")
                total_songs += songs_added

            added_count += 1

            # MusicBrainz rate limit: 1 request per second
            sleep(1.1)

        except Exception as e:
            print(f"  ✗ Error creating item: {e}")
            error_count += 1

    # Summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Total artists processed: {len(POPULAR_ARTISTS)}")
    print(f"Artists added to database: {added_count}")
    print(f"Songs added to database: {total_songs}")
    print(f"Already in database: {skipped_count}")
    print(f"Errors: {error_count}")
    print("="*60)
    print(f"\nYou can now visit: http://localhost:8000/category/music-artists/")


if __name__ == '__main__':
    main()

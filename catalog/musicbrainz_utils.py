"""
Utility functions for fetching artist data from MusicBrainz.
"""
import re
import requests
from time import sleep

# MusicBrainz requires a User-Agent with contact info
HEADERS = {
    'User-Agent': 'PopQuiz/1.0 (https://github.com/yourusername/popquiz)',
    'Accept': 'application/json',
}

# Rate limiting: MusicBrainz allows 1 request per second
RATE_LIMIT_DELAY = 1.0


def extract_musicbrainz_id(url):
    """
    Extract MusicBrainz artist ID (UUID) from a URL.
    Accepts URLs like:
    - https://musicbrainz.org/artist/5b11f4ce-a62d-471e-81fc-a69a8278c7da
    - https://musicbrainz.org/artist/5b11f4ce-a62d-471e-81fc-a69a8278c7da/releases
    - 5b11f4ce-a62d-471e-81fc-a69a8278c7da (just the UUID)
    """
    if not url:
        return None

    # If it's already just a UUID
    uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
    if re.match(uuid_pattern, url.strip(), re.IGNORECASE):
        return url.strip().lower()

    # Extract from URL
    match = re.search(r'/artist/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})', url, re.IGNORECASE)
    if match:
        return match.group(1).lower()

    return None


def search_artists(query, limit=10):
    """
    Search MusicBrainz for artists by name.

    Returns a list of dicts, each with:
    - musicbrainz_id: str (UUID)
    - name: str
    - disambiguation: str (e.g. "American rock band")
    - type: str (Person, Group, Orchestra, etc.)
    - area: str (country/city)
    """
    if not query or not query.strip():
        return []

    try:
        sleep(RATE_LIMIT_DELAY)
        resp = requests.get(
            "https://musicbrainz.org/ws/2/artist/",
            headers=HEADERS,
            params={'query': query.strip(), 'fmt': 'json', 'limit': limit},
            timeout=15,
        )
        if resp.status_code != 200:
            return []

        results = []
        for artist in resp.json().get('artists', []):
            mb_id = artist.get('id')
            name = artist.get('name')
            if not mb_id or not name:
                continue
            area = ''
            if artist.get('area'):
                area = artist['area'].get('name', '')
            results.append({
                'musicbrainz_id': mb_id,
                'name': name,
                'disambiguation': artist.get('disambiguation', ''),
                'type': artist.get('type', ''),
                'area': area,
            })

        return results

    except (requests.RequestException, ValueError, KeyError):
        return []


def search_release_groups(query, limit=10):
    """
    Search MusicBrainz for release groups (albums, singles, EPs) by title.

    Returns a list of dicts, each with:
    - musicbrainz_id: str (UUID)
    - title: str
    - artist: str (artist name)
    - release_type: str (Album, Single, EP, etc.)
    - year: int or None
    """
    if not query or not query.strip():
        return []

    try:
        sleep(RATE_LIMIT_DELAY)
        resp = requests.get(
            "https://musicbrainz.org/ws/2/release-group/",
            headers=HEADERS,
            params={'query': query.strip(), 'fmt': 'json', 'limit': limit},
            timeout=15,
        )
        if resp.status_code != 200:
            return []

        results = []
        for rg in resp.json().get('release-groups', []):
            mb_id = rg.get('id')
            title = rg.get('title')
            if not mb_id or not title:
                continue

            artist_parts = []
            for credit in rg.get('artist-credit', []):
                if isinstance(credit, dict) and 'artist' in credit:
                    artist_parts.append(credit['artist'].get('name', ''))
                    joinphrase = credit.get('joinphrase', '')
                    if joinphrase:
                        artist_parts.append(joinphrase)
            artist = ''.join(artist_parts).strip()

            year = None
            first_release = rg.get('first-release-date', '')
            if first_release:
                year_match = re.match(r'(\d{4})', first_release)
                if year_match:
                    year = int(year_match.group(1))

            results.append({
                'musicbrainz_id': mb_id,
                'title': title,
                'artist': artist,
                'release_type': rg.get('primary-type', ''),
                'year': year,
            })

        return results

    except (requests.RequestException, ValueError, KeyError):
        return []


def extract_musicbrainz_release_id(url):
    """
    Extract MusicBrainz release-group ID (UUID) from a URL.
    Accepts URLs like:
    - https://musicbrainz.org/release-group/5b11f4ce-a62d-471e-81fc-a69a8278c7da
    - 5b11f4ce-a62d-471e-81fc-a69a8278c7da (just the UUID)
    """
    if not url:
        return None

    # If it's already just a UUID
    uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
    if re.match(uuid_pattern, url.strip(), re.IGNORECASE):
        return url.strip().lower()

    # Extract from release-group URL
    match = re.search(r'/release-group/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})', url, re.IGNORECASE)
    if match:
        return match.group(1).lower()

    return None


def fetch_release_data(musicbrainz_url):
    """
    Fetch release-group data from MusicBrainz given a URL or MusicBrainz ID.

    Returns a dict with:
    - title: str (release title)
    - artist: str (artist name)
    - year: int or None (first release year)
    - release_type: str (Album, Single, EP, etc.)
    - musicbrainz_id: str (UUID)

    Returns None if fetch fails.
    """
    mb_id = extract_musicbrainz_release_id(musicbrainz_url)
    if not mb_id:
        return None

    try:
        sleep(RATE_LIMIT_DELAY)

        rg_url = f"https://musicbrainz.org/ws/2/release-group/{mb_id}"
        resp = requests.get(rg_url, headers=HEADERS, params={'inc': 'artist-credits', 'fmt': 'json'}, timeout=15)
        if resp.status_code != 200:
            return None

        data = resp.json()

        title = data.get('title')
        if not title:
            return None

        # Build artist name from artist-credit list (handles joint artists like "A & B")
        artist_parts = []
        for credit in data.get('artist-credit', []):
            if isinstance(credit, dict) and 'artist' in credit:
                artist_parts.append(credit['artist'].get('name', ''))
                joinphrase = credit.get('joinphrase', '')
                if joinphrase:
                    artist_parts.append(joinphrase)
        artist = ''.join(artist_parts).strip()

        # Extract year from first-release-date
        year = None
        first_release = data.get('first-release-date', '')
        if first_release:
            year_match = re.match(r'(\d{4})', first_release)
            if year_match:
                year = int(year_match.group(1))

        release_type = data.get('primary-type', '')

        # Try to fetch cover art from Cover Art Archive
        poster_url = None
        try:
            sleep(RATE_LIMIT_DELAY)
            caa_resp = requests.get(
                f"https://coverartarchive.org/release-group/{mb_id}",
                headers=HEADERS,
                timeout=10,
                allow_redirects=True,
            )
            if caa_resp.status_code == 200:
                caa_data = caa_resp.json()
                for image in caa_data.get('images', []):
                    if image.get('front'):
                        thumbnails = image.get('thumbnails', {})
                        poster_url = thumbnails.get('500') or thumbnails.get('large') or image.get('image')
                        break
        except (requests.RequestException, ValueError, KeyError):
            pass  # Cover art is optional; continue without it

        return {
            'title': title,
            'artist': artist,
            'year': year,
            'release_type': release_type,
            'musicbrainz_id': mb_id,
            'poster_url': poster_url,
        }

    except (requests.RequestException, ValueError, KeyError):
        return None


def fetch_artist_data(musicbrainz_url, fetch_songs=True, max_songs=100):
    """
    Fetch artist data from MusicBrainz given a URL or MusicBrainz ID.

    Args:
        musicbrainz_url: Artist URL or UUID
        fetch_songs: Whether to fetch the artist's songs/recordings
        max_songs: Maximum number of songs to fetch

    Returns a dict with:
    - title: str (artist name)
    - musicbrainz_id: str (UUID)
    - area: str or None (country/location)
    - disambiguation: str or None (disambiguating info)
    - poster_url: str or None (artist image, if available)
    - songs: list of dicts with song data (if fetch_songs=True)
        Each song dict has: title, musicbrainz_id, year, album

    Returns None if fetch fails.
    """
    mb_id = extract_musicbrainz_id(musicbrainz_url)
    if not mb_id:
        return None

    try:
        # First, fetch artist info
        # Rate limiting
        sleep(RATE_LIMIT_DELAY)

        artist_url = f"https://musicbrainz.org/ws/2/artist/{mb_id}"
        resp = requests.get(artist_url, headers=HEADERS, params={'fmt': 'json'}, timeout=15)
        if resp.status_code != 200:
            return None

        data = resp.json()

        # Extract artist info
        artist_name = data.get('name')
        if not artist_name:
            return None

        disambiguation = data.get('disambiguation', '')

        # Extract area (country)
        area = None
        if data.get('area'):
            area = data['area'].get('name')
        elif data.get('begin-area'):
            area = data['begin-area'].get('name')

        # Try to get artist image from Cover Art Archive
        # Note: MusicBrainz doesn't directly provide artist images
        # We could potentially fetch from their first release group
        poster_url = None

        result = {
            'title': artist_name,
            'musicbrainz_id': mb_id,
            'area': area,
            'disambiguation': disambiguation,
            'poster_url': poster_url,
        }

        # Fetch songs/recordings if requested using browse endpoint
        # The browse endpoint provides first-release-date which the artist endpoint doesn't
        if fetch_songs:
            songs = []
            seen_titles = set()  # Avoid duplicates

            # Rate limiting before second request
            sleep(RATE_LIMIT_DELAY)

            # Use browse recordings endpoint to get recordings with first-release-date
            recordings_url = "https://musicbrainz.org/ws/2/recording"
            recordings_params = {
                'fmt': 'json',
                'artist': mb_id,
                'limit': max_songs,
                'offset': 0
            }

            recordings_resp = requests.get(recordings_url, headers=HEADERS, params=recordings_params, timeout=15)
            if recordings_resp.status_code == 200:
                recordings_data = recordings_resp.json()

                for recording in recordings_data.get('recordings', []):
                    title = recording.get('title')
                    if not title or title in seen_titles:
                        continue

                    seen_titles.add(title)

                    # Extract year from first release date
                    year = None
                    if 'first-release-date' in recording:
                        year_match = re.match(r'(\d{4})', recording['first-release-date'])
                        if year_match:
                            year = int(year_match.group(1))

                    # Note: The browse recordings endpoint doesn't include release details
                    # To get album names, we'd need additional API calls per recording
                    # For now, we'll leave album empty and users can add it manually
                    album = ''

                    songs.append({
                        'title': title,
                        'musicbrainz_id': recording.get('id'),
                        'year': year,
                        'album': album,
                    })

            result['songs'] = songs

        return result

    except (requests.RequestException, ValueError, KeyError):
        return None

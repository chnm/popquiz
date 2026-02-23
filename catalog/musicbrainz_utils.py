"""
Utility functions for fetching music data from MusicBrainz.
"""
import logging
import re
import requests
from time import sleep

logger = logging.getLogger(__name__)

# MusicBrainz requires a User-Agent with contact info
HEADERS = {
    'User-Agent': 'PopQuiz/1.0 (https://github.com/yourusername/popquiz)',
    'Accept': 'application/json',
}

# Rate limiting: MusicBrainz allows 1 request per second
RATE_LIMIT_DELAY = 1.0

# Cover Art Archive retry settings
CAA_MAX_RETRIES = 3
CAA_RETRY_DELAYS = [1, 2, 3]  # seconds between retries


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


def search_recordings(query, limit=10):
    """
    Search MusicBrainz for recordings (songs) by title.

    Returns a list of dicts, each with:
    - musicbrainz_id: str (recording UUID)
    - title: str (recording/song title)
    - artist: str (artist name)
    - artist_id: str (artist MusicBrainz UUID)
    - release_group_id: str or None (first release-group UUID)
    - release_group_title: str (album/release name, or '')
    - year: int or None
    """
    if not query or not query.strip():
        return []

    try:
        sleep(RATE_LIMIT_DELAY)
        resp = requests.get(
            "https://musicbrainz.org/ws/2/recording/",
            headers=HEADERS,
            params={'query': query.strip(), 'fmt': 'json', 'limit': limit},
            timeout=15,
        )
        if resp.status_code != 200:
            return []

        results = []
        for rec in resp.json().get('recordings', []):
            mb_id = rec.get('id')
            title = rec.get('title')
            if not mb_id or not title:
                continue

            # Extract artist from artist-credit
            artist_name = ''
            artist_id = None
            artist_parts = []
            for credit in rec.get('artist-credit', []):
                if isinstance(credit, dict) and 'artist' in credit:
                    if not artist_id:
                        artist_id = credit['artist'].get('id')
                    artist_parts.append(credit['artist'].get('name', ''))
                    joinphrase = credit.get('joinphrase', '')
                    if joinphrase:
                        artist_parts.append(joinphrase)
            artist_name = ''.join(artist_parts).strip()

            # Extract release-group info from the first release
            release_group_id = None
            release_group_title = ''
            releases = rec.get('releases', [])
            if releases:
                first_release = releases[0]
                rg = first_release.get('release-group', {})
                release_group_id = rg.get('id')
                release_group_title = first_release.get('title', '')

            # Extract year
            year = None
            first_release_date = rec.get('first-release-date', '')
            if first_release_date:
                year_match = re.match(r'(\d{4})', first_release_date)
                if year_match:
                    year = int(year_match.group(1))

            results.append({
                'musicbrainz_id': mb_id,
                'title': title,
                'artist': artist_name,
                'artist_id': artist_id,
                'release_group_id': release_group_id,
                'release_group_title': release_group_title,
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


def _fetch_cover_art(release_group_id):
    """
    Fetch cover art URL from Cover Art Archive for a release-group.

    Uses multiple retries with increasing delays to handle intermittent
    SSL/connection issues with coverartarchive.org.

    Returns the cover art URL string, or None if unavailable.
    """
    caa_url = f"https://coverartarchive.org/release-group/{release_group_id}"

    for attempt in range(CAA_MAX_RETRIES):
        try:
            delay = CAA_RETRY_DELAYS[attempt] if attempt < len(CAA_RETRY_DELAYS) else CAA_RETRY_DELAYS[-1]
            sleep(delay)
            logger.info("CAA fetch attempt %d for %s", attempt + 1, release_group_id)
            caa_resp = requests.get(
                caa_url,
                headers=HEADERS,
                timeout=15,
                allow_redirects=True,
            )
            if caa_resp.status_code == 200:
                caa_data = caa_resp.json()
                for image in caa_data.get('images', []):
                    if image.get('front'):
                        thumbnails = image.get('thumbnails', {})
                        url = thumbnails.get('500') or thumbnails.get('large') or image.get('image')
                        if url:
                            logger.info("CAA cover art found: %s", url)
                            return url
                logger.info("CAA returned 200 but no front cover image found")
                return None
            elif caa_resp.status_code == 404:
                logger.info("CAA returned 404 — no cover art exists for %s", release_group_id)
                return None
            else:
                logger.warning("CAA returned status %d on attempt %d", caa_resp.status_code, attempt + 1)
        except (requests.RequestException, ValueError, KeyError) as e:
            logger.warning("CAA fetch error on attempt %d: %s: %s", attempt + 1, type(e).__name__, e)

    logger.warning("CAA fetch failed after %d attempts for %s", CAA_MAX_RETRIES, release_group_id)
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

        # Build artist name and extract primary artist ID from artist-credit list
        artist_parts = []
        artist_id = None
        for credit in data.get('artist-credit', []):
            if isinstance(credit, dict) and 'artist' in credit:
                if not artist_id:
                    artist_id = credit['artist'].get('id')
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
        poster_url = _fetch_cover_art(mb_id)

        return {
            'title': title,
            'artist': artist,
            'artist_id': artist_id,
            'year': year,
            'release_type': release_type,
            'musicbrainz_id': mb_id,
            'poster_url': poster_url,
        }

    except (requests.RequestException, ValueError, KeyError):
        return None


def fetch_release_tracks(release_group_id):
    """
    Fetch the tracklist for a release group from MusicBrainz.

    Gets the first release in the release-group and extracts its tracklist.

    Returns a list of dicts, each with:
    - musicbrainz_id: str (recording UUID)
    - title: str (track title)
    - position: int (track number)

    Returns empty list if fetch fails.
    """
    if not release_group_id:
        return []

    try:
        sleep(RATE_LIMIT_DELAY)
        resp = requests.get(
            "https://musicbrainz.org/ws/2/release",
            headers=HEADERS,
            params={
                'release-group': release_group_id,
                'inc': 'recordings',
                'fmt': 'json',
                'limit': 1,
            },
            timeout=15,
        )
        if resp.status_code != 200:
            return []

        data = resp.json()
        releases = data.get('releases', [])
        if not releases:
            return []

        tracks = []
        seen_ids = set()
        for medium in releases[0].get('media', []):
            for track in medium.get('tracks', []):
                recording = track.get('recording', {})
                rec_id = recording.get('id')
                if not rec_id or rec_id in seen_ids:
                    continue
                seen_ids.add(rec_id)
                tracks.append({
                    'musicbrainz_id': rec_id,
                    'title': recording.get('title', track.get('title', '')),
                    'position': track.get('position', 0),
                })

        return tracks

    except (requests.RequestException, ValueError, KeyError):
        return []


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

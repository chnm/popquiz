"""
Utility functions for fetching movie/person data from The Movie Database (TMDB).

TMDB has a free API that provides complete, accurate filmographies unlike IMDB
which now requires JavaScript rendering.  Requires a free API key from
https://www.themoviedb.org/settings/api  (set TMDB_API_KEY env var).
"""
import logging
import requests

logger = logging.getLogger(__name__)

TMDB_BASE = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"

HEADERS = {
    'User-Agent': 'Mozilla/5.0',
    'Accept': 'application/json',
}


def _get(path, api_key, **params):
    """Make a GET request to the TMDB API."""
    params['api_key'] = api_key
    try:
        resp = requests.get(f"{TMDB_BASE}{path}", params=params, headers=HEADERS, timeout=15)
        if resp.status_code == 200:
            return resp.json()
    except requests.RequestException as e:
        logger.error(f"TMDB request failed for {path}: {e}")
    return None


def search_people(name, api_key):
    """
    Search TMDB for people by name.

    Returns a list of dicts, each with:
    - name: str
    - tmdb_id: int
    - known_for: str (e.g. "Acting")
    - known_titles: str (e.g. "The Fly, House of Wax")
    - profile_url: str or "" (headshot image URL)

    Returns empty list if search fails or no results.
    """
    if not name or not name.strip():
        return []

    data = _get('/search/person', api_key, query=name.strip(), include_adult=False)
    if not data:
        return []

    results = []
    for person in data.get('results', [])[:10]:
        known_for_titles = [
            kf.get('title') or kf.get('name') or ''
            for kf in person.get('known_for', [])
            if kf.get('title') or kf.get('name')
        ]
        profile_path = person.get('profile_path') or ''
        results.append({
            'name': person.get('name', ''),
            'tmdb_id': person.get('id'),
            'known_for': person.get('known_for_department', ''),
            'known_titles': ', '.join(known_for_titles[:4]),
            'profile_url': f"{TMDB_IMAGE_BASE}{profile_path}" if profile_path else '',
        })
    return results


def fetch_actor_filmography_tmdb(tmdb_person_id, api_key, limit=50):
    """
    Fetch the most popular movies where this person acted.

    Returns a dict with:
    - name: str (person's name from TMDB)
    - movies: list of dicts, each with tmdb_id, title, year

    Sorted by TMDB popularity score and capped at `limit` (default 50)
    so actors with huge filmographies don't flood the database.

    Returns None if fetch fails.
    """
    # Get person details for name
    person_data = _get(f'/person/{tmdb_person_id}', api_key)
    if not person_data:
        return None
    name = person_data.get('name', '')

    # Get movie credits
    credits = _get(f'/person/{tmdb_person_id}/movie_credits', api_key)
    if not credits:
        return None

    movies = []
    seen_ids = set()
    for entry in credits.get('cast', []):
        tmdb_id = entry.get('id')
        if not tmdb_id or tmdb_id in seen_ids:
            continue
        # Skip adult content and direct-to-video
        if entry.get('adult'):
            continue
        if entry.get('video'):
            continue
        # Skip TV Movies / TV Specials (TMDB genre ID 10770)
        if 10770 in (entry.get('genre_ids') or []):
            continue
        # Skip minor roles and cameos — only include top 10 billed cast
        if (entry.get('order') or 0) > 10:
            continue
        seen_ids.add(tmdb_id)
        year = None
        release = entry.get('release_date') or ''
        if release and len(release) >= 4:
            try:
                year = int(release[:4])
            except ValueError:
                pass
        movies.append({
            'tmdb_id': tmdb_id,
            'title': entry.get('title', ''),
            'year': year,
            'popularity': entry.get('popularity') or 0,
        })

    # Sort by TMDB popularity (highest first) and take top N
    movies.sort(key=lambda x: -x['popularity'])
    movies = movies[:limit]

    # Re-sort the final list by year (newest first) for display
    movies.sort(key=lambda x: -(x['year'] or 0))
    return {'name': name, 'movies': movies}


def fetch_director_filmography_tmdb(tmdb_person_id, api_key):
    """
    Fetch all movies this person directed.

    Returns a dict with:
    - name: str
    - movies: list of dicts, each with tmdb_id, title, year

    Returns None if fetch fails.
    """
    person_data = _get(f'/person/{tmdb_person_id}', api_key)
    if not person_data:
        return None
    name = person_data.get('name', '')

    credits = _get(f'/person/{tmdb_person_id}/movie_credits', api_key)
    if not credits:
        return None

    movies = []
    seen_ids = set()
    for entry in credits.get('crew', []):
        if entry.get('job') != 'Director':
            continue
        tmdb_id = entry.get('id')
        if not tmdb_id or tmdb_id in seen_ids:
            continue
        if entry.get('adult'):
            continue
        if entry.get('video'):
            continue
        seen_ids.add(tmdb_id)
        year = None
        release = entry.get('release_date') or ''
        if release and len(release) >= 4:
            try:
                year = int(release[:4])
            except ValueError:
                pass
        movies.append({
            'tmdb_id': tmdb_id,
            'title': entry.get('title', ''),
            'year': year,
        })

    movies.sort(key=lambda x: -(x['year'] or 0))
    return {'name': name, 'movies': movies}


def fetch_movie_details_tmdb(tmdb_id, api_key):
    """
    Fetch full movie details from TMDB including the IMDB ID.

    Returns a dict with:
    - imdb_id: str (e.g. "tt0055304")
    - title: str
    - year: int or None
    - director: str (first director's name, or "")
    - genre: str (comma-separated, up to 3)
    - image_source_url: str (full poster URL, or "")
    - imdb_url: str

    Returns None if fetch fails or movie has no IMDB ID.
    """
    data = _get(f'/movie/{tmdb_id}', api_key, append_to_response='credits')
    if not data:
        return None

    imdb_id = data.get('imdb_id') or ''
    if not imdb_id or not imdb_id.startswith('tt'):
        return None

    # Year from release_date
    year = None
    release = data.get('release_date') or ''
    if release and len(release) >= 4:
        try:
            year = int(release[:4])
        except ValueError:
            pass

    # Director from credits
    director = ''
    credits = data.get('credits') or {}
    for crew_member in credits.get('crew', []):
        if crew_member.get('job') == 'Director':
            director = crew_member.get('name', '')
            break

    # Genres (up to 3)
    genres = [g['name'] for g in data.get('genres', [])[:3]]
    genre = ', '.join(genres)

    # Poster URL
    poster_path = data.get('poster_path') or ''
    image_source_url = f"{TMDB_IMAGE_BASE}{poster_path}" if poster_path else ''

    return {
        'imdb_id': imdb_id,
        'title': data.get('title', ''),
        'year': year,
        'years_running': '',
        'director': director,
        'genre': genre,
        'image_source_url': image_source_url,
        'imdb_url': f"https://www.imdb.com/title/{imdb_id}/",
        'adult': data.get('adult', False),
        'runtime': data.get('runtime') or 0,
    }

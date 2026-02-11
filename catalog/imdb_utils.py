"""
Utility functions for fetching movie data from IMDB.
"""
import html
import re
import requests

# User-Agent header to avoid being blocked
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
}


def extract_imdb_id(url):
    """
    Extract IMDB ID from a URL.
    Accepts URLs like:
    - https://www.imdb.com/title/tt0111161/
    - https://imdb.com/title/tt0111161
    - https://m.imdb.com/title/tt0111161/
    - tt0111161 (just the ID)
    """
    if not url:
        return None

    # If it's already just an ID
    if re.match(r'^tt\d+$', url.strip()):
        return url.strip()

    # Extract from URL
    match = re.search(r'(tt\d+)', url)
    if match:
        return match.group(1)

    return None


def fetch_movie_data(imdb_url):
    """
    Fetch movie data from IMDB given a URL or IMDB ID.

    Returns a dict with:
    - title: str
    - year: int or None
    - director: str or None
    - genre: str or None (comma-separated list of genres)
    - imdb_id: str
    - imdb_url: str (cleaned canonical URL)
    - poster_url: str or None

    Returns None if fetch fails.
    """
    imdb_id = extract_imdb_id(imdb_url)
    if not imdb_id:
        return None

    canonical_url = f"https://www.imdb.com/title/{imdb_id}/"

    try:
        resp = requests.get(canonical_url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            return None

        page_html = resp.text

        # Extract title
        title = None
        # Try og:title first (English title on US IMDB site)
        og_title = re.search(r'<meta property="og:title" content="([^"]+)"', page_html)
        if og_title:
            # Clean up the title - IMDB includes extra metadata we need to remove
            title = og_title.group(1)
            title = re.sub(r'\s*\|.*$', '', title)  # Remove pipe separator and everything after (genres, etc.)
            title = re.sub(r'\s*⭐\s*[\d.]+', '', title)  # Remove star emoji and rating
            title = re.sub(r'\s*\(\d{4}\)', '', title)  # Remove year in parentheses
            title = re.sub(r'\s*-\s*IMDb\s*$', '', title)  # Remove - IMDb suffix
            title = html.unescape(title)  # Decode HTML entities like &amp;
            title = title.strip()
        else:
            # Fallback to JSON-LD if og:title not available
            json_title = re.search(r'"name":\s*"([^"]+)"', page_html)
            if json_title:
                title = html.unescape(json_title.group(1))

        if not title:
            return None

        # Extract year
        year = None
        year_match = re.search(r'"datePublished":\s*"(\d{4})', page_html)
        if year_match:
            year = int(year_match.group(1))
        else:
            # Try release year from title or other sources
            year_alt = re.search(r'<title>[^<]+\((\d{4})\)', page_html)
            if year_alt:
                year = int(year_alt.group(1))

        # Extract poster URL
        poster_url = None
        og_image = re.search(r'<meta property="og:image" content="([^"]+)"', page_html)
        if og_image:
            poster_url = og_image.group(1)
            # Convert to larger resolution
            if 'media-amazon.com' in poster_url:
                poster_url = re.sub(r'_V1_.*\.jpg', '_V1_.jpg', poster_url)

        # Extract director
        director = None
        # Try JSON-LD director field
        director_match = re.search(r'"director":\s*\[?\s*\{\s*"@type":\s*"Person",\s*"name":\s*"([^"]+)"', page_html)
        if director_match:
            director = director_match.group(1)
        else:
            # Try alternative pattern for multiple directors
            directors_match = re.search(r'"director":\s*\[([^\]]+)\]', page_html)
            if directors_match:
                # Extract first director's name
                first_director = re.search(r'"name":\s*"([^"]+)"', directors_match.group(1))
                if first_director:
                    director = first_director.group(1)

        # Extract genres
        genre = None
        # Try JSON-LD genre field (can be a string or array)
        genre_match = re.search(r'"genre":\s*(\[.*?\]|"[^"]+?")', page_html)
        if genre_match:
            genre_data = genre_match.group(1)
            if genre_data.startswith('['):
                # It's an array, extract all genre strings
                genres = re.findall(r'"([^"]+)"', genre_data)
                if genres:
                    genre = ', '.join(genres[:3])  # Take first 3 genres
            else:
                # It's a single string
                genre = genre_data.strip('"')

        return {
            'title': title,
            'year': year,
            'director': director,
            'genre': genre,
            'imdb_id': imdb_id,
            'imdb_url': canonical_url,
            'poster_url': poster_url,
        }

    except requests.RequestException:
        return None


def search_directors_by_name(director_name):
    """
    Search IMDB for directors by name.

    Returns a list of dicts, each with:
    - name: str (person's full name)
    - imdb_id: str (nm#######)
    - known_for: str (description of what they're known for)

    Returns empty list if search fails or no results found.
    """
    if not director_name or not director_name.strip():
        return []

    search_url = f"https://www.imdb.com/find/?q={requests.utils.quote(director_name.strip())}&s=nm"

    try:
        resp = requests.get(search_url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            return []

        page_html = resp.text
        results = []

        # IMDB search results use this structure:
        # <a...href="/name/nm#######/?ref=..."...aria-label="Name">
        # The href comes before aria-label, and includes query parameters
        result_pattern = r'<a[^>]+href="/name/(nm\d+)/\?[^"]*"[^>]+aria-label="([^"]+)"'

        matches = re.finditer(result_pattern, page_html)
        seen_ids = set()

        for match in matches:
            imdb_id = match.group(1)
            name = html.unescape(match.group(2)).strip()

            # Avoid duplicates
            if imdb_id in seen_ids:
                continue
            seen_ids.add(imdb_id)

            # Try to extract profession information from nearby context
            start_pos = max(0, match.start() - 1000)
            end_pos = min(len(page_html), match.end() + 1000)
            context = page_html[start_pos:end_pos]

            # Look for profession data in nlib-professions element
            known_for = ""
            professions_match = re.search(r'data-testid="nlib-professions"[^>]*>(.*?)</ul>', context, re.DOTALL)
            if professions_match:
                professions_html = professions_match.group(1)
                # Extract all <li> items
                profession_items = re.findall(r'<li[^>]*>([^<]+)</li>', professions_html)
                if profession_items:
                    # Clean and join professions
                    professions = [html.unescape(p.strip()) for p in profession_items]
                    known_for = ', '.join(professions)

            results.append({
                'name': name,
                'imdb_id': imdb_id,
                'known_for': known_for,
            })

            # Limit to top 10 results
            if len(results) >= 10:
                break

        return results

    except requests.RequestException:
        return []


def fetch_director_filmography(director_id):
    """
    Fetch a director's filmography - movies they directed.

    Filters out:
    - TV Series, TV Movies, TV Episodes, TV Mini-Series
    - Shorts, Video Games, Videos

    Returns a dict with:
    - name: str (director's name)
    - movies: list of dicts, each with:
      - title: str
      - year: int or None
      - imdb_id: str (tt#######)

    Returns None if fetch fails.
    """
    if not director_id:
        return None

    # Extract just the ID if a URL was passed
    if director_id.startswith('http'):
        id_match = re.search(r'(nm\d+)', director_id)
        if id_match:
            director_id = id_match.group(1)
        else:
            return None

    # Ensure it starts with nm
    if not re.match(r'^nm\d+$', director_id):
        return None

    canonical_url = f"https://www.imdb.com/name/{director_id}/"

    try:
        resp = requests.get(canonical_url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            return None

        page_html = resp.text

        # Extract director name from og:title meta tag
        name = None
        name_match = re.search(r'<meta property="og:title" content="([^"]+)"', page_html)
        if name_match:
            name = name_match.group(1).replace(' - IMDb', '').strip()

        if not name:
            return None

        # Find all movie links with titles from the director's page
        # Pattern: <a...href="/title/tt#######/?ref=..."...aria-label="Title (Year)">
        movie_pattern = r'<a[^>]+href="/title/(tt\d+)/\?[^"]*"[^>]*aria-label="([^"]+)"'

        potential_movies = []
        matches = re.finditer(movie_pattern, page_html)
        seen_ids = set()

        for match in matches:
            imdb_id = match.group(1)
            aria_label = html.unescape(match.group(2)).strip()

            # Skip duplicates
            if imdb_id in seen_ids:
                continue

            # Filter out TV content and non-movies by checking the aria-label
            # When you visit a director's IMDB page, the filmography mainly shows
            # their directing work. We just need to filter out TV shows and shorts.
            is_not_movie = (
                'TV Series' in aria_label or
                'TV Mini-Series' in aria_label or
                'TV Mini Series' in aria_label or
                'TV Movie' in aria_label or
                'TV Episode' in aria_label or
                'TV Special' in aria_label or
                '(TV Series' in aria_label or
                '(TV Mini-Series' in aria_label or
                '(TV Movie' in aria_label or
                'Short' in aria_label or
                '(Short' in aria_label or
                'Video Game' in aria_label or
                '(Video Game' in aria_label or
                '(Video' in aria_label or
                'Music Video' in aria_label or
                '(Music Video' in aria_label
            )

            # Skip non-movies
            if is_not_movie:
                continue

            seen_ids.add(imdb_id)

            # Extract year from aria-label
            year = None
            year_match = re.search(r'\((\d{4})\)', aria_label)
            if year_match:
                year = int(year_match.group(1))

            # Clean up title - remove year and extra markers
            title = re.sub(r'\s*\(\d{4}\)\s*$', '', aria_label)
            title = title.strip()

            if title:
                potential_movies.append({
                    'title': title,
                    'year': year,
                    'imdb_id': imdb_id,
                })

        # Sort by year (newest first), then by title
        potential_movies.sort(key=lambda x: (-x['year'] if x['year'] else 0, x['title'].lower()))

        return {
            'name': name,
            'movies': potential_movies,
        }

    except requests.RequestException:
        return None

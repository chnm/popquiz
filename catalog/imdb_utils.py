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


def extract_director_id(url):
    """
    Extract IMDB director/person ID from a URL.
    Accepts URLs like:
    - https://www.imdb.com/name/nm0001392/
    - https://imdb.com/name/nm0001392
    - nm0001392 (just the ID)
    """
    if not url:
        return None

    # If it's already just an ID
    if re.match(r'^nm\d+$', url.strip()):
        return url.strip()

    # Extract from URL
    match = re.search(r'(nm\d+)', url)
    if match:
        return match.group(1)

    return None


def search_directors_by_name(director_name):
    """
    Search IMDB for directors by name.

    Returns a list of dicts, each with:
    - name: str (director's full name)
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
        directors = []

        # Look for name search results
        # IMDB now uses aria-label for names in search results
        # Pattern: <a...href="/name/nm#######/..."...aria-label="Name">
        result_pattern = r'<a[^>]+href="/name/(nm\d+)/[^"]*"[^>]+aria-label="([^"]+)"'

        # Find all person results
        matches = re.finditer(result_pattern, page_html)
        seen_ids = set()

        for match in matches:
            imdb_id = match.group(1)
            name = html.unescape(match.group(2)).strip()

            # Avoid duplicates
            if imdb_id in seen_ids:
                continue
            seen_ids.add(imdb_id)

            # Try to extract "known for" information
            # Look for text near this result
            start_pos = max(0, match.start() - 500)
            end_pos = min(len(page_html), match.end() + 500)
            context = page_html[start_pos:end_pos]

            # Try to find credits/known-for information
            known_for = ""
            known_for_match = re.search(r'<li[^>]*class="[^"]*known-for[^"]*"[^>]*>([^<]+)</li>', context)
            if not known_for_match:
                # Try alternative pattern
                known_for_match = re.search(r'<span[^>]*class="[^"]*ipc-metadata[^"]*"[^>]*>([^<]+)</span>', context)

            if known_for_match:
                known_for = html.unescape(known_for_match.group(1)).strip()

            directors.append({
                'name': name,
                'imdb_id': imdb_id,
                'known_for': known_for,
            })

            # Limit to top 10 results
            if len(directors) >= 10:
                break

        return directors

    except requests.RequestException:
        return []


def fetch_director_filmography(director_url):
    """
    Fetch a director's filmography from their IMDB page.

    Returns a dict with:
    - name: str (director's name)
    - movies: list of dicts, each with:
      - title: str
      - year: int or None
      - imdb_id: str

    Returns None if fetch fails.
    """
    director_id = extract_director_id(director_url)
    if not director_id:
        return None

    canonical_url = f"https://www.imdb.com/name/{director_id}/"

    try:
        resp = requests.get(canonical_url, headers=HEADERS, timeout=15)
        if resp.status_code != 200:
            return None

        page_html = resp.text

        # Extract director name
        name = None
        name_match = re.search(r'<meta property="og:title" content="([^"]+)"', page_html)
        if name_match:
            name = name_match.group(1).replace(' - IMDb', '').strip()

        if not name:
            return None

        # Extract filmography - IMDB now uses aria-label for movie titles
        movies = []

        # Pattern: <a...href="/title/tt#######/..."...aria-label="Title (Year)">
        # The aria-label contains both title and year
        movie_pattern = r'<a[^>]+href="/title/(tt\d+)/[^"]*"[^>]+aria-label="([^"]+)"'

        # Find all movies on the page
        movie_matches = re.finditer(movie_pattern, page_html)
        seen_ids = set()

        for match in movie_matches:
            imdb_id = match.group(1)
            aria_label = html.unescape(match.group(2)).strip()

            # Skip duplicates
            if imdb_id in seen_ids:
                continue
            seen_ids.add(imdb_id)

            # Extract year from aria-label (usually at the end in parentheses)
            year = None
            year_match = re.search(r'\((\d{4})\)', aria_label)
            if year_match:
                year = int(year_match.group(1))

            # Clean up title - remove year, actor names, etc.
            title = aria_label
            # Remove " in Title" patterns (for actor credits)
            title = re.sub(r'^[^"]+ in ', '', title)
            # Remove year in parentheses
            title = re.sub(r'\s*\(\d{4}\)\s*$', '', title)
            title = title.strip()

            if title:
                movies.append({
                    'title': title,
                    'year': year,
                    'imdb_id': imdb_id,
                })

        # Sort by year (newest first), then by title
        movies.sort(key=lambda x: (-x['year'] if x['year'] else 0, x['title'].lower()))

        return {
            'name': name,
            'movies': movies,
        }

    except requests.RequestException:
        return None

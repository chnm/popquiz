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
            # Remove year suffix and " - IMDb" suffix
            title = og_title.group(1)
            title = re.sub(r'\s*\(\d{4}\)\s*$', '', title)  # Remove (2023)
            title = re.sub(r'\s*-\s*IMDb\s*$', '', title)   # Remove - IMDb
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

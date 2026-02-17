# PopQuiz - AI Agent Context

This document provides comprehensive context for AI agents working on the PopQuiz codebase.

**IMPORTANT**: Before working on this codebase, read `README.md` to understand what PopQuiz does and who it's for. This provides essential context about the app's purpose and user experience.

## AI Agent Guidelines

**IMPORTANT WORKFLOW**: When making changes to the codebase, always follow this workflow:

1. **Understand** - Read relevant code and documentation
2. **Implement** - Make the necessary changes
3. **Test** - Verify changes work (restart server if needed)
4. **Commit** - Always commit successful modifications

**Why committing matters:**
- Ensures work is tracked in version control
- Enables deployment of changes to production
- Creates audit trail for modifications
- Allows rollback if issues arise
- Documents what was changed and why

**Golden Rule**: If a modification is successful and improves the codebase, commit it immediately. Don't wait for multiple changes to accumulate.

## Project Overview

**PopQuiz** is a Django-based web application for team voting on pop culture items (primarily movies). It features a Tinder-style swipe interface, team rankings, compatibility comparisons, and various statistical views organized by decade, director, and genre.

**Tech Stack:**
- Django 5.2+ (Python web framework)
- SQLite database (db.sqlite3)
- Tailwind CSS for styling
- Vanilla JavaScript for interactivity
- IMDB integration for movie data
- uv for Python package management

## Architecture

PopQuiz follows standard Django project structure with three main apps:

### 1. **catalog** - Core Content Management
- Manages categories (e.g., "Movies", "TV Shows") and items (individual movies)
- Handles IMDB data fetching and movie metadata (title, year, director, genre, poster)
- Provides category browsing, item adding, and movie detail views
- Statistics views: team rankings, decade rankings, eclectic tastes, divisive movies

### 2. **ratings** - Rating System
- Manages user ratings with 5-point scale: Loved (🤩), Liked (🙂), Okay (😐), Disliked (😕), Hated (😡), plus No Rating/Haven't Seen (⏭️)
- Numeric values: Loved (+2), Liked (+1), Okay (0), Disliked (-1), Hated (-2)
- AJAX-based rating API for smooth UX
- Enforces unique ratings per user/item combination
- Rating scale displayed consistently from Hated (left) to Loved (right) across all UI

### 3. **accounts** - User Management & Social Features
- User registration, login, logout
- Profile pages showing user's rating history
- User comparison feature showing compatibility and disagreements
- Profile sorting: by category, title, year, director, genre, rating, popularity

## Database Models

### catalog.Category
```python
name = CharField(max_length=100)
slug = SlugField(unique=True)
```

### catalog.Item
```python
category = ForeignKey(Category)
title = CharField(max_length=255)
year = PositiveIntegerField(null=True, blank=True)
director = CharField(max_length=255, blank=True)
genre = CharField(max_length=255, blank=True)  # Comma-separated
imdb_id = CharField(max_length=20, unique=True)
imdb_url = URLField(blank=True)
poster_url = URLField(blank=True)
added_by = ForeignKey(User, null=True)
created_at = DateTimeField(auto_now_add=True)
```

### ratings.Rating
```python
user = ForeignKey(User)
item = ForeignKey(Item)
rating = CharField(choices=['loved', 'liked', 'okay', 'disliked', 'hated', 'no_rating'])
updated_at = DateTimeField(auto_now=True)
# Unique constraint: (user, item)
# Note: Database table name is 'ratings_rating' (using db_table meta option)
```

## URL Structure

### Admin
- `/admin/` - Django admin site

### Public Pages
- `/` - Home dashboard with voting progress and team members (HomeView)
- `/accounts/login/` - User login (CustomLoginView)
- `/accounts/logout/` - User logout (CustomLogoutView)
- `/accounts/register/` - User registration (RegisterView)
- `/accounts/` - django-allauth URLs (includes social auth, password reset, email verification, etc.)

### Category & Movies
- `/category/<slug:slug>/` - Browse all items in category with inline rating buttons (CategoryDetailView)
- `/category/<slug:slug>/add/` - Add new item to category (AddItemView)
- `/category/<slug:slug>/rate/` - Swipe rating interface (SwipeRatingView)
- `/category/<slug:category_slug>/movie/<int:item_id>/` - Individual movie detail with all ratings and user rating editor (MovieDetailView)

### Statistics
- `/category/<slug:slug>/stats/` - Team rankings with simple average algorithm (StatsView)
- `/category/<slug:slug>/decades/` - Movies grouped and ranked by decade (DecadeStatsView)
- `/category/<slug:slug>/eclectic/` - Users with most unique opinions (EclecticView)
- `/category/<slug:slug>/divisive/` - Movies with most polarized ratings (DivisiveView)

### User Features
- `/profile/<str:username>/` - User's rating history and stats (ProfileView)
- `/profile/<str:username>/?sort=<option>` - Sort by: title, year, director, genre, rating, popularity
- `/compare/<str:username1>/<str:username2>/` - Compare two users' tastes (CompareUsersView)
- `/compare/<str:username1>/<str:username2>/<str:username3>/` - Compare three users' tastes (3-way Venn)

### API & Rating
- `/api/rate/` - POST endpoint for AJAX rating (rate_api)
- `/rate/` - Rating form submission endpoint (rate_view)

## Key Features & Implementation

### 1. IMDB Data Fetching
**File:** `catalog/imdb_utils.py`

- `extract_imdb_id(url)` - Extracts IMDB ID from URL or validates ID
- `fetch_movie_data(imdb_url)` - Scrapes IMDB for title, year, director, genre, poster
- Uses regex parsing of IMDB HTML (no official API)
- Prioritizes English titles using `og:title` meta tag
- Handles HTML entity decoding for special characters

### 2. Ranking Algorithm
PopQuiz uses **simple averaging** for rankings:

```python
# Each rating has a numeric value
# Loved: +2, Liked: +1, Okay: 0, Disliked: -1, Hated: -2
average_score = sum(rating_values) / count(ratings)
# Score is then converted to 0-100 scale for display
display_score = ((average_score + 2) / 4) * 100
```

The average score represents the mean rating across all users who have rated the item. Items with no ratings show a score of 0.

### 3. Swipe Rating UX
**Files:** `catalog/views.py:SwipeRatingView`, `catalog/templates/catalog/swipe_rating.html`

- Tinder-style card interface with 5-point rating scale
- AJAX rating submission without page reload
- Shows next unrated item immediately
- Large emoji buttons (text-xl and text-4xl) for easy clicking
- Rating scale ordered Hated → Disliked → Okay → Liked → Loved (left to right)
- Mobile-optimized with touch gestures
- Fixed layout heights to prevent jitter
- Separate mobile and desktop layouts for optimal UX

### 4. Profile Grouping
**File:** `accounts/views.py:ProfileView`

User ratings can be grouped by:
- **Category** (default) - Groups by movie category
- **Director** - All movies by each director
- **Genre** - Movies by genre (can appear in multiple groups)
- **Title** - Alphabetical sorting
- **Year** - Chronological sorting
- **Rating** - Grouped by user's rating (Loved/Liked/Okay/Disliked/Hated)
- **Popularity** - Sorted by total rating count

Profile page features:
- Stats bar showing rating distribution with color-coded segments
- Large emoji badges on movie poster grids
- Enlarged emojis (text-lg) in header legend for better visibility

### 5. User Comparison
**File:** `accounts/views.py:CompareUsersView`

Categories of agreement/disagreement:
- Both Love (both rated Loved)
- Both Hate (both rated Hated)
- Both Like/Dislike/Okay (matching ratings at other levels)
- User1 loves, User2 hates (opposite extremes)
- User1 hates, User2 loves (opposite extremes)
- Other disagreements (mixed ratings)
- Only User1 rated
- Only User2 rated

Supports both 2-way and 3-way comparisons (Venn diagram style)

## File Structure

```
popquiz/
├── manage.py                    # Django management script
├── pyproject.toml               # Python dependencies and project metadata
├── uv.lock                      # Locked dependency versions
├── db.sqlite3                   # SQLite database
├── static/                      # Static assets
│   └── images/
│       └── founder.jpg          # Founder photo used on home page
├── templates/                   # Shared templates
│   └── base.html               # Base template with navigation
├── popquiz/                     # Django project settings
│   ├── settings.py
│   └── urls.py                 # Root URL configuration
├── catalog/                     # Main content app
│   ├── models.py               # Category, Item models
│   ├── views.py                # All catalog views
│   ├── urls.py                 # Catalog URL patterns
│   ├── imdb_utils.py           # IMDB scraping utilities
│   ├── admin.py                # Django admin configuration
│   ├── templatetags/
│   │   └── custom_filters.py  # Template filters
│   └── templates/catalog/
│       ├── home.html           # Landing page with featured movie
│       ├── category_detail.html # Browse items with inline rating buttons
│       ├── swipe_rating.html   # Swipe rating interface
│       ├── add_item.html       # Add new item via IMDB
│       ├── movie_detail.html   # Movie details with user rating editor
│       ├── stats.html          # Team rankings
│       ├── decade_stats.html   # Rankings by decade
│       ├── eclectic.html       # Most unique opinions
│       └── divisive.html       # Most polarized movies
├── ratings/                     # Rating app
│   ├── models.py               # Rating model
│   ├── views.py                # Rating logic
│   └── urls.py                 # Rating API endpoints
└── accounts/                    # User management app
    ├── models.py               # Custom User model
    ├── views.py                # Auth & profile views
    ├── urls.py                 # Account URL patterns
    └── templates/accounts/
        ├── register.html
        ├── login.html
        ├── profile.html        # User rating history
        └── compare.html        # User comparison (2-way and 3-way)
```

## Development Setup

This project uses **uv** for fast, reliable Python package management. All dependencies are defined in `pyproject.toml`.

```bash
# Install uv (if not already installed)
# See: https://docs.astral.sh/uv/getting-started/installation/
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies and sync environment
uv sync

# Run migrations
uv run python manage.py migrate

# Create superuser (if needed)
uv run python manage.py createsuperuser

# Run development server
uv run python manage.py runserver

# Access at http://localhost:8000
```

### Managing Dependencies

```bash
# Add a new dependency
uv add package-name

# Add a development dependency
uv add --dev package-name

# Remove a dependency
uv remove package-name

# Update all dependencies
uv sync --upgrade
```

## Deployment & Server Management

**CRITICAL**: This container environment is the production website hosted at **https://popquiz.rrchnm.org**. SSL/TLS is handled by reverse proxy outside this container.

### Background Deployment

The server MUST run in the background using `nohup` to persist across sessions:

```bash
# Use the Makefile for all deployment operations
make deploy    # Full deployment (migrate, collectstatic, start in background)
make status    # Check if server is running
make stop      # Stop the server
make restart   # Restart the server
make logs      # View recent logs
```

### Manual Deployment Process

If deploying manually (without Makefile):

```bash
# 1. Check for pending migrations
uv run python manage.py showmigrations

# 2. Apply any pending migrations
uv run python manage.py migrate

# 3. Collect static files (for production-like setup)
uv run python manage.py collectstatic --noinput

# 4. Start the server in background on 0.0.0.0:8000
nohup uv run python manage.py runserver 0.0.0.0:8000 > /tmp/popquiz.log 2>&1 &
echo $! > .pid
```

**Why these steps matter:**
- **showmigrations**: Verifies database schema is up-to-date
- **migrate**: Applies any pending database migrations to avoid runtime errors
- **collectstatic**: Ensures all static files (CSS, JS, images) are properly collected with WhiteNoise
- **0.0.0.0:8000**: Makes the server accessible from all network interfaces (not just localhost)
- **nohup**: Runs server in background, not tied to current terminal session
- **.pid file**: Tracks process ID across sessions for stop/restart operations (gitignored)
- **/tmp/popquiz.log**: All logs written to /tmp for debugging
- **uv**: Fast Python package manager that ensures correct dependencies are used

### Health Checks

Always verify the server is running after changes:

```bash
# Check if process is running
make status

# View recent logs
make logs

# If not running, restart
make restart
```

### Process Management

- **PID File**: `.pid` stores the server process ID (gitignored)
- **Logs**: All output written to `/tmp/popquiz.log`
- **Background Mode**: Server persists across terminal disconnections

## Common Tasks

### Adding a New Movie via IMDB
Movies are typically added through the web UI at `/category/<slug>/add/`, which:
1. Takes IMDB URL or ID
2. Fetches metadata via `fetch_movie_data()`
3. Creates Item in database
4. Associates with current user as `added_by`

### Modifying Rankings Algorithm
Edit the ranking logic in `catalog/views.py:StatsView`:
- Look for Bayesian average calculation
- Adjust `m` (minimum votes) or `C` (mean rating) as needed

### Adding New Rating Types
If adding beyond the current 5-point scale:
1. Update `ratings.models.Rating.Level` enum
2. Update rating UI in `swipe_rating.html` and other templates
3. Update rating counting logic in statistics views
4. Update profile display logic
5. Update numeric value mappings for score calculations

### Customizing Profile Sorting
Edit `accounts/views.py:ProfileView`:
- Add new sort option to `sort_by` parameter handling
- Implement sorting logic in the appropriate section
- Add UI button in `accounts/templates/accounts/profile.html`

## Important Notes & Gotchas

### 1. IMDB Scraping Fragility
The IMDB scraping in `imdb_utils.py` uses regex parsing of HTML, which can break if IMDB changes their page structure. If movie data stops fetching:
- Check if IMDB HTML structure changed
- Update regex patterns in `fetch_movie_data()`
- IMDB may rate-limit or block requests - 0.5s delay added between requests

**Recent fixes:**
- Fixed variable name conflict: renamed `html` variable to `page_html` to avoid overwriting the `html` module
- Enhanced title parsing to strip metadata: removes star ratings (⭐), genres after pipe (|), and years in parentheses
- IMDB now includes extra metadata in og:title that must be cleaned

### 2. Genre Field Format
Genres are stored as comma-separated strings (e.g., "Drama, Thriller, Crime"):
- When splitting, always use `.split(',')` and `.strip()`
- Movies can appear in multiple genre groups in profile view
- Max 3 genres extracted from IMDB to keep it concise

### 3. Static Files
- Static directory was in `.gitignore`, but we force-added founder images
- WhiteNoise is configured for production static file serving
- Remember to run `uv run python manage.py collectstatic --noinput` after static file changes
- Current founder image: `founder_transparent.png` (used on home dashboard)
- `founder.jpg` also exists but not currently used
- WhiteNoise serves static files in production without needing nginx
- Static files use cache-busting hashes in production (e.g., `founder_transparent.d6d8442a3c35.png`)

### 4. Rating Uniqueness
The `(user, item)` unique constraint means:
- Users can only rate once per item
- Changing rating updates existing record (doesn't create duplicate)
- `NO_RATING` (Haven't Seen) is the default for unrated items

### 5. Authentication Requirements
Most views require authentication:
- Use `@method_decorator(login_required)` on class-based views
- Unauthenticated users see simplified home page
- Public views: home, login, register

### 6. Mobile Optimization
The app is heavily optimized for mobile:
- Tailwind responsive classes (md: breakpoints)
- Touch-friendly rating interface with large emoji buttons
- Hamburger menu for navigation on small screens
- Fixed heights prevent layout jitter during AJAX updates
- Separate mobile and desktop layouts for rating interface

### 7. Emoji Sizing for UX
Emojis are intentionally enlarged throughout the app for better visibility and usability:
- **Swipe rating page**: text-xl (mobile) and text-4xl (desktop) for main buttons
- **Category detail page**: text-xl for inline rating buttons
- **Stats page**: text-lg for rating breakdown and legend
- **Profile page**: text-lg for header legend, text-sm for movie cards, text-base for badges
- **Home dashboard**: text-lg for featured movie legend and recent activity icons
- **Movie detail page**: text-xl for user rating buttons
- Use `inline-flex items-center gap-1` with `leading-none` on emoji spans to prevent vertical misalignment

### 8. Rating Scale Order
The rating scale is consistently displayed as **Hated → Disliked → Okay → Liked → Loved** (left to right) across all UI:
- Aligns with natural expectation (negative on left, positive on right)
- Matches color progression (red → orange → yellow → green → purple)
- Applied to: swipe interface, stats page, profile page, movie detail page, comparison pages

### 9. Simple Average Ranking
- Items with 0 ratings get score of 0 (filtered from rankings)
- Score calculated as: `((average_rating + 2) / 4) * 100` to convert -2/+2 range to 0-100 scale
- All ratings weighted equally (no Bayesian adjustment)

### 10. Profile Performance
Profile pages with many ratings can be slow:
- Uses `.select_related()` to reduce queries
- Annotates rating counts for popularity sorting
- Consider pagination for users with 100+ ratings

### 11. Movie Detail Page User Rating
The movie detail page (`MovieDetailView`) allows users to see and change their ratings:
- User's current rating is fetched and highlighted with colored background + ring indicator
- Rating buttons positioned below team rating summary
- Uses form POST to `/rate/` with `next` parameter to redirect back to same page
- Rating scale follows standard Hated → Loved order
- Large emoji buttons (text-xl) for easy clicking

### 12. Social Media Meta Tags
The base template includes comprehensive social media meta tags:
- **SEO**: Meta description for search engines
- **Open Graph**: For Facebook, LinkedIn sharing (og:title, og:description, og:image, og:url)
- **Twitter Card**: For Twitter sharing with large image preview
- **Favicon**: RRCHNM favicon
- All tags use Django template blocks for per-page customization
- Default social image: `founder_transparent.png`
- Individual pages can override meta tags by extending blocks (e.g., `{% block og_title %}Custom Title{% endblock %}`)

## Deployment Workflow

**PRODUCTION ENVIRONMENT**: This codebase runs the live website at https://popquiz.rrchnm.org. All changes should be:
1. Tested locally/in development
2. Committed to git with clear messages
3. Deployed using the Makefile
4. Verified via health checks

### Pre-Deployment Checklist

Before deploying changes:
- [ ] Check for remote updates: `git fetch origin`
- [ ] Prompt user to pull if behind remote
- [ ] Commit all changes to git
- [ ] Review changes are correct and tested

### Deployment Steps

```bash
# 1. Fetch remote changes
git fetch origin

# 2. If behind remote, prompt user to pull
git status  # Check if behind

# 3. Deploy application
make deploy

# 4. Verify deployment
make status
make logs
```

## Git Workflow

### Remote Synchronization

**IMPORTANT**: Always check for remote updates before making changes:

```bash
# Fetch from remote
git fetch origin

# Check if behind remote
git status

# If behind, prompt user: "Remote changes detected. Pull changes before proceeding?"
```

### Committing Changes

**CRITICAL**: Always commit successful modifications to the codebase. This ensures work is tracked and can be deployed.

**When to commit:**
- After successfully implementing a feature or fix
- After updating dependencies or configuration
- After refactoring that passes existing functionality checks
- When tests pass (if applicable)
- Before switching to a different task or feature

**Commit workflow:**
```bash
# 1. Check what files have changed
git status

# 2. Review the changes
git diff

# 3. Stage the relevant files
git add <file1> <file2> ...
# Or stage all changes: git add .

# 4. Commit with a descriptive message
git commit -m "Brief summary of changes

- Detailed point 1
- Detailed point 2
- Why this change was needed

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"

# 5. Verify the commit
git log -1 --stat
```

**Commit message best practices:**
- Use imperative mood ("Add feature" not "Added feature")
- First line: concise summary (50 chars or less)
- Blank line after summary
- Detailed explanation in body (wrap at 72 chars)
- Reference issue numbers if applicable
- Explain WHY, not just WHAT

**DO NOT commit:**
- Sensitive data (.env files, credentials, API keys)
- Generated files that are in .gitignore (staticfiles/, __pycache__, etc.)
- Incomplete or broken changes
- Debug code or temporary test files

Recent significant commits:
- Fix IMDB title parsing to strip metadata (ratings, genres, years)
- Fix variable name conflict in IMDB fetching (html module vs variable)
- Add Open Graph, Twitter Card, and SEO meta tags
- Update dashboard to use transparent founder image
- Add README.md with user-friendly app description
- AI agent workflow and git commit guidelines documentation
- WhiteNoise configuration for production static file serving
- Migration to uv for Python package management
- Image processing and background removal
- Director and genre metadata backfilling
- Profile grouping by director/genre
- Movie detail pages
- Bayesian ranking algorithm
- Swipe voting UX improvements
- Mobile hamburger menu
- RRCHNM branding

## Testing Approach

Currently no automated tests. Manual testing focuses on:
- Vote submission and updating
- IMDB data fetching with various URL formats
- Ranking calculations with edge cases
- Mobile responsive behavior
- Profile sorting options
- User comparison accuracy

## API Conventions

### AJAX Voting
**POST** `/api/vote/`

Request:
```json
{
  "item_id": 123,
  "choice": "yes"  // "yes", "no", "meh"
}
```

Response:
```json
{
  "success": true,
  "next_item_id": 124
}
```

## Future Enhancement Ideas

Based on codebase patterns, natural extensions:
- Add TV shows, books, or music as separate categories
- Export/import voting data
- Email notifications for new items
- User avatars and profiles
- Advanced filtering (by decade, director, genre on main pages)
- Vote history/timeline
- Recommendation engine based on taste similarity
- Dark mode
- Public/private categories

## Help & Resources

- Django Documentation: https://docs.djangoproject.com/
- Tailwind CSS: https://tailwindcss.com/docs
- SQLite: https://www.sqlite.org/docs.html

## License & Credits

PopQuiz is developed for team use. The app uses publicly available IMDB data for educational/personal purposes.

---

*Last Updated: 2026-02-17*
*This document is maintained for AI agent context and onboarding.*

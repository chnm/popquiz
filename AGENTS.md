# PopQuiz - AI Agent Context

This document provides comprehensive context for AI agents working on the PopQuiz codebase.

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
- Statistics views: team rankings, decade rankings, eclectic tastes

### 2. **votes** - Voting System
- Manages user votes with four choices: Yes, No, Meh, No Answer
- AJAX-based voting API for smooth UX
- Enforces unique votes per user/item combination

### 3. **accounts** - User Management & Social Features
- User registration, login, logout
- Profile pages showing user's voting history
- User comparison feature showing compatibility and disagreements
- Profile sorting: by category, title, year, director, genre, vote, popularity

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

### votes.Vote
```python
user = ForeignKey(User)
item = ForeignKey(Item)
choice = CharField(choices=['yes', 'no', 'meh', 'no_answer'])
updated_at = DateTimeField(auto_now=True)
# Unique constraint: (user, item)
```

## URL Structure

### Public Pages
- `/` - Home dashboard with voting progress and team members
- `/accounts/login/` - User login
- `/accounts/register/` - User registration

### Category & Movies
- `/category/<slug>/` - Browse all items in category
- `/category/<slug>/add/` - Add new item to category
- `/category/<slug>/vote/` - Swipe voting interface
- `/category/<slug>/movie/<id>/` - Individual movie detail with all votes

### Statistics
- `/category/<slug>/stats/` - Team rankings (Bayesian average algorithm)
- `/category/<slug>/decades/` - Movies grouped and ranked by decade
- `/category/<slug>/eclectic/` - Users with most unique opinions

### User Features
- `/profile/<username>/` - User's voting history and stats
- `/profile/<username>/?sort=<option>` - Sort by: title, year, director, genre, vote, popularity
- `/compare/<user1>/<user2>/` - Compare two users' tastes

### API
- `/api/vote/` - POST endpoint for AJAX voting

## Key Features & Implementation

### 1. IMDB Data Fetching
**File:** `catalog/imdb_utils.py`

- `extract_imdb_id(url)` - Extracts IMDB ID from URL or validates ID
- `fetch_movie_data(imdb_url)` - Scrapes IMDB for title, year, director, genre, poster
- Uses regex parsing of IMDB HTML (no official API)
- Prioritizes English titles using `og:title` meta tag
- Handles HTML entity decoding for special characters

### 2. Ranking Algorithm
PopQuiz uses **Bayesian averaging** for fair rankings, especially with limited votes:

```python
bayesian_score = (v / (v + m)) * R + (m / (v + m)) * C
# v = votes for this item
# m = minimum votes threshold (e.g., 3)
# R = average rating for this item
# C = mean rating across all items
```

This prevents items with 1-2 highly positive votes from dominating the rankings.

### 3. Swipe Voting UX
**Files:** `catalog/views.py:SwipeVoteView`, `catalog/templates/catalog/swipe_vote.html`

- Tinder-style card interface
- AJAX voting without page reload
- Shows next unvoted item immediately
- Mobile-optimized with touch gestures
- Fixed layout heights to prevent jitter

### 4. Profile Grouping
**File:** `accounts/views.py:ProfileView`

User votes can be grouped by:
- **Category** (default) - Groups by movie category
- **Director** - All movies by each director
- **Genre** - Movies by genre (can appear in multiple groups)
- **Title** - Alphabetical sorting
- **Year** - Chronological sorting
- **Vote** - Grouped by user's choice (Yes/Meh/No)
- **Popularity** - Sorted by total vote count

### 5. User Comparison
**File:** `accounts/views.py:CompareUsersView`

Categories of agreement/disagreement:
- Both Love (both voted Yes)
- Both Hate (both voted No)
- Both Meh (both voted Meh)
- User1 loves, User2 hates
- User1 hates, User2 loves
- Other disagreements (Meh vs Yes/No)
- Only User1 voted
- Only User2 voted

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
│       ├── home.html           # Landing page
│       ├── category_detail.html
│       ├── swipe_vote.html     # Voting interface
│       ├── add_item.html
│       ├── movie_detail.html
│       ├── stats.html
│       ├── decade_stats.html
│       └── eclectic.html
├── votes/                       # Voting app
│   ├── models.py               # Vote model
│   ├── views.py                # Voting logic
│   └── urls.py                 # Vote API endpoints
└── accounts/                    # User management app
    ├── models.py               # (Uses Django's User model)
    ├── views.py                # Auth & profile views
    ├── urls.py                 # Account URL patterns
    └── templates/accounts/
        ├── register.html
        ├── login.html
        └── profile.html
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

## Starting the App Server

**IMPORTANT**: When starting the app server, always follow these steps in order:

```bash
# 1. Check for pending migrations
uv run python manage.py showmigrations

# 2. Apply any pending migrations
uv run python manage.py migrate

# 3. Collect static files (for production-like setup)
uv run python manage.py collectstatic --noinput

# 4. Start the server on 0.0.0.0:8000 (accessible from all network interfaces)
uv run python manage.py runserver 0.0.0.0:8000
```

**Why these steps matter:**
- **showmigrations**: Verifies database schema is up-to-date
- **migrate**: Applies any pending database migrations to avoid runtime errors
- **collectstatic**: Ensures all static files (CSS, JS, images) are properly collected
- **0.0.0.0:8000**: Makes the server accessible from other devices on the network (not just localhost)
- **uv**: Fast Python package manager that ensures correct dependencies are used

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

### Adding New Vote Types
If adding beyond Yes/No/Meh:
1. Update `votes.models.Vote.Choice` enum
2. Update voting UI in `swipe_vote.html`
3. Update vote counting logic in statistics views
4. Update profile display logic

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

### 2. Genre Field Format
Genres are stored as comma-separated strings (e.g., "Drama, Thriller, Crime"):
- When splitting, always use `.split(',')` and `.strip()`
- Movies can appear in multiple genre groups in profile view
- Max 3 genres extracted from IMDB to keep it concise

### 3. Static Files
- Static directory was in `.gitignore`, but we force-added the founder image
- Remember to run `uv run python manage.py collectstatic --noinput` for production
- Founder image uses `{% load static %}` template tag
- WhiteNoise serves static files in production without needing nginx

### 4. Vote Uniqueness
The `(user, item)` unique constraint means:
- Users can only vote once per item
- Changing vote updates existing record (doesn't create duplicate)
- `NO_ANSWER` is the default for unvoted items

### 5. Authentication Requirements
Most views require authentication:
- Use `@method_decorator(login_required)` on class-based views
- Unauthenticated users see simplified home page
- Public views: home, login, register

### 6. Mobile Optimization
The app is heavily optimized for mobile:
- Tailwind responsive classes (md: breakpoints)
- Touch-friendly voting interface
- Hamburger menu for navigation on small screens
- Fixed heights prevent layout jitter during AJAX updates

### 7. Bayesian Ranking Edge Cases
- Items with 0 votes get score of 0 (filtered from rankings)
- Items with 1-2 votes are heavily pulled toward mean rating
- Adjust `m` threshold based on team size (currently ~3)

### 8. Profile Performance
Profile pages with many votes can be slow:
- Uses `.select_related()` to reduce queries
- Annotates vote counts for popularity sorting
- Consider pagination for users with 100+ votes

## Git Workflow

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

*Last Updated: 2026-02-09*
*This document is maintained for AI agent context and onboarding.*

# AGENTS.md

> For feature specifications, business rules, and domain models, see [SPEC.md](./SPEC.md).

---

## Table of Contents

- [Project Overview](#project-overview)
- [Tech Stack](#tech-stack)
  - [Package Management](#package-management)
  - [Backend](#backend)
  - [Frontend](#frontend)
  - [Database](#database)
- [Project Initialization](#project-initialization)
- [Project Structure](#project-structure)
- [Architecture](#architecture)
  - [Django Apps](#django-apps)
  - [Database Models](#database-models)
  - [URL Structure](#url-structure)
- [Authentication & Authorization](#authentication--authorization)
  - [User Auth](#user-auth)
  - [Protected Views](#protected-views)
- [Development Workflow](#development-workflow)
  - [Version Control](#version-control)
  - [Database Migrations](#database-migrations)
  - [Debugging & Logging](#debugging--logging)
  - [Serving the Application](#serving-the-application)
  - [Testing Approach](#testing-approach)
- [Best Practices & Key Conventions](#best-practices--key-conventions)
- [Notes for AI Agents](#notes-for-ai-agents)

---

## Project Overview

**PopQuiz** is a Django-based web application for team voting on pop culture items (primarily movies). It features a Tinder-style swipe interface, team rankings, compatibility comparisons, and various statistical views organized by decade, director, and genre.

**Purpose:**
- Facilitate team discussions about movies through structured voting
- Reveal team rankings based on aggregated preferences
- Enable taste compatibility analysis between team members
- Provide engaging swipe-based voting interface

**Target Users:**
Friend groups, work teams, film clubs, or any group that wants to discover their collective taste and compare preferences.

**Key Technical Features:**
- IMDB integration for automatic movie metadata fetching
- Real-time AJAX voting without page reloads
- Bayesian averaging for fair ranking calculations
- Social authentication via Slack OAuth
- Mobile-optimized responsive design

**Production Environment:**
Hosted at https://popquiz.rrchnm.org with WhiteNoise for static file serving and reverse proxy handling SSL/TLS.

---

## Tech Stack

### Package Management

- **Manager:** uv (fast Python package manager)
- **Configuration:** `pyproject.toml` for dependencies and project metadata
- **Lock File:** `uv.lock` (committed to repository)
- **Key Commands:**
  - `uv sync` - Install/sync dependencies
  - `uv add <package>` - Add new dependency
  - `uv remove <package>` - Remove dependency
  - `uv run python` - Run Python with project environment

### Backend

- **Runtime:** Python 3.13+
- **Framework:** Django 5.2+ (latest stable)
- **Key Libraries:**
  - **django-allauth** - Social authentication (Slack OAuth)
  - **WhiteNoise** - Static file serving in production
  - **python-dotenv** - Environment variable management
  - **requests** - HTTP library for IMDB scraping
- **API Pattern:** Traditional Django views with AJAX endpoints for voting
- **Static Files:** Tailwind CSS for styling, vanilla JavaScript for interactivity

### Frontend

- **Framework:** Django templates (server-side rendering)
- **CSS Framework:** Tailwind CSS 3.x (utility-first)
- **JavaScript:** Vanilla ES6+ (no framework)
- **Build Tools:** None required (Tailwind CDN via template)
- **Key Features:**
  - AJAX-based voting with fetch API
  - Swipe gestures for mobile voting
  - Dynamic progress bars and real-time updates
  - Responsive hamburger menu navigation

### Database

- **Type:** SQLite (single-file database)
- **ORM:** Django ORM (built-in)
- **Location:** `/workspace/db.sqlite3`
- **Migrations:** Django's built-in migration system
- **Connection:** Single-threaded SQLite (suitable for team-size usage)
- **Backup:** Handled externally (container-level)

---

## Project Initialization

**Prerequisites:**
- Python 3.13+ (managed by uv)
- uv package manager installed
- Git for version control
- Sudo access for database permissions (if needed)

**Setup Steps:**

1. **Clone Repository**
   ```bash
   git clone <repository-url>
   cd popquiz
   ```

2. **Install Dependencies**
   ```bash
   uv sync
   ```

3. **Environment Configuration**
   - Environment variables (optional, has defaults):
     - `SECRET_KEY` - Django secret key
     - `DEBUG` - Debug mode (True/False)
     - `ALLOWED_HOSTS` - Comma-separated host list
     - `CSRF_TRUSTED_ORIGINS` - Comma-separated HTTPS origins
     - `ALLAUTH_SLACK_CLIENT_ID` - Slack OAuth client ID
     - `ALLAUTH_SLACK_CLIENT_SECRET` - Slack OAuth secret

4. **Database Setup**
   ```bash
   # Apply migrations
   uv run python manage.py migrate

   # Create superuser (optional)
   uv run python manage.py createsuperuser
   ```

5. **Collect Static Files**
   ```bash
   uv run python manage.py collectstatic --noinput
   ```

6. **Start Development Server**
   ```bash
   uv run python manage.py runserver 0.0.0.0:8000
   ```

7. **Verify Installation**
   - Access: http://localhost:8000
   - Admin: http://localhost:8000/admin/
   - Check for staticfiles warning (expected if /workspace/static doesn't exist)

**Common Setup Issues:**
- **Database permissions:** See "Database Migrations" section for permission fixes
- **WhiteNoise warnings:** Ignore staticfiles.W004 if not using custom static directory
- **Import errors:** Run `uv sync` to ensure dependencies are installed

---

## Project Structure

```
popquiz/
├── manage.py                    # Django management script
├── pyproject.toml               # Python dependencies and metadata
├── uv.lock                      # Locked dependency versions
├── Makefile                     # Deployment automation commands
├── .pid                         # Process ID for background server (gitignored)
├── db.sqlite3                   # SQLite database (gitignored)
├── README.md                    # User-facing app description
├── AGENTS.md                    # Technical documentation (this file)
├── SPEC.md                      # Product specifications
├── static/                      # Static assets (select files tracked)
│   └── images/                  # Images (founder photos, etc.)
├── staticfiles/                 # Collected static files (gitignored)
├── templates/                   # Shared Django templates
│   ├── base.html               # Base template with navigation
│   ├── account/                # django-allauth overrides
│   └── socialaccount/          # Social auth templates
├── popquiz/                     # Django project settings
│   ├── settings.py             # Main configuration
│   └── urls.py                 # Root URL configuration
├── catalog/                     # Core content management app
│   ├── models.py               # Category, Item models
│   ├── views.py                # All catalog views
│   ├── urls.py                 # Catalog URL patterns
│   ├── imdb_utils.py           # IMDB scraping utilities
│   ├── admin.py                # Admin configuration
│   ├── templatetags/           # Custom template filters
│   └── templates/catalog/      # Catalog-specific templates
├── ratings/                     # Rating system app
│   ├── models.py               # Rating model
│   ├── views.py                # Rating submission logic
│   └── urls.py                 # Rating API endpoints
└── accounts/                    # User management app
    ├── models.py               # Custom User model
    ├── views.py                # Auth & profile views
    ├── adapter.py              # Slack OAuth adapter
    ├── urls.py                 # Account URL patterns
    └── templates/accounts/     # Account templates
```

**Key Directory Purposes:**

- **popquiz/** - Project-level settings, DO NOT add business logic here
- **catalog/** - Core app for categories and items (movies), main business logic
- **ratings/** - Handles all rating/voting functionality, separate concern
- **accounts/** - User authentication, profiles, and comparisons
- **templates/** - Shared templates used across apps
- **static/** - Source static files (manually added, not generated)
- **staticfiles/** - Generated by collectstatic, served by WhiteNoise

**Naming Conventions:**
- Files: snake_case for Python modules
- Templates: snake_case.html
- URLs: kebab-case in URL patterns
- Models: PascalCase for classes

**When to Create New Files:**
- Add views to existing views.py in respective app
- Create new templates in app's templates/ subdirectory
- Add utilities to existing utils files or create new ones
- Keep related functionality together in the same app

---

## Architecture

PopQuiz follows standard Django MTV (Model-Template-View) architecture with three main apps handling distinct responsibilities.

### Django Apps

**1. catalog** - Core Content Management
- Manages categories (e.g., "Movies") and items (individual movies)
- Handles IMDB data fetching and metadata (title, year, director, genre, poster)
- Provides category browsing, item adding, and movie detail views
- Statistics views: team rankings, decade rankings, eclectic tastes, divisive movies
- Key Files: `models.py` (Category, Item), `imdb_utils.py` (scraping), `views.py` (all catalog views)

**2. ratings** - Rating System
- Manages user ratings with 5-point Likert scale
- Rating levels: Loved (🤩 +2), Liked (🙂 +1), Okay (😐 0), Disliked (😕 -1), Hated (😡 -2), No Rating (⏭️)
- AJAX-based rating API for smooth UX without page reloads
- Enforces unique ratings per user/item combination via database constraint
- Key Files: `models.py` (Rating model), `views.py` (rate_api endpoint)

**3. accounts** - User Management & Social Features
- User registration, login, logout (with Slack OAuth)
- Profile pages showing user's rating history with multiple sort options
- User comparison feature showing compatibility and disagreements
- Custom social account adapter for syncing Slack profile data
- Key Files: `models.py` (User with avatar_url), `views.py` (ProfileView, CompareUsersView), `adapter.py`

### Database Models

**catalog.Category**
```python
name = CharField(max_length=100)
slug = SlugField(unique=True)
```

**catalog.Item**
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

**ratings.Rating**
```python
user = ForeignKey(User)
item = ForeignKey(Item)
rating = CharField(choices=[
    ('loved', 'Loved'),
    ('liked', 'Liked'),
    ('okay', 'Okay'),
    ('disliked', 'Disliked'),
    ('hated', 'Hated'),
    ('no_rating', 'No Rating')
])
updated_at = DateTimeField(auto_now=True)
# Unique constraint: (user, item)
# Database table: 'ratings_rating'
```

**accounts.User** (extends AbstractUser)
```python
# Inherits: username, email, first_name, last_name, password
avatar_url = URLField(blank=True)  # Synced from Slack
```

### URL Structure

**Admin:**
- `/admin/` - Django admin site

**Public Pages:**
- `/` - Home dashboard (HomeView)
- `/accounts/login/` - Login (allauth)
- `/accounts/logout/` - Logout (allauth)
- `/accounts/register/` - Registration (allauth)
- `/accounts/slack/login/` - Slack OAuth flow

**Category & Movies:**
- `/category/<slug:slug>/` - Browse items with inline rating (CategoryDetailView)
- `/category/<slug:slug>/add/` - Add new item via IMDB (AddItemView)
- `/category/<slug:slug>/rate/` - Swipe rating interface (SwipeRatingView)
- `/category/<slug:category_slug>/movie/<int:item_id>/` - Movie detail (MovieDetailView)

**Statistics:**
- `/category/<slug:slug>/stats/` - Team rankings (StatsView)
- `/category/<slug:slug>/decades/` - Rankings by decade (DecadeStatsView)
- `/category/<slug:slug>/eclectic/` - Users with unique opinions (EclecticView)
- `/category/<slug:slug>/divisive/` - Polarized movies (DivisiveView)

**User Features:**
- `/profile/<str:username>/` - User's rating history (ProfileView)
- `/profile/<str:username>/?sort=<option>` - Sort by: category, title, year, director, genre, rating, popularity
- `/compare/<str:username1>/<str:username2>/` - Compare two users (CompareUsersView)
- `/compare/<str:username1>/<str:username2>/<str:username3>/` - Compare three users (3-way Venn)

**API Endpoints:**
- `/api/rate/` - POST endpoint for AJAX rating (rate_api)
- `/rate/` - Traditional form POST for rating (rate_view)

---

## Authentication & Authorization

### User Auth

**Authentication Strategy:** Session-based authentication with optional Slack OAuth

**Login/Signup Flow:**
1. **Traditional Auth:**
   - Registration: username, email, password
   - Email verification: DISABLED (no SMTP configured)
   - Login: username or email with password
   - Session stored in database (django_session table)

2. **Slack OAuth:**
   - User clicks "Sign in with Slack"
   - Redirected to Slack OAuth consent page
   - Callback to `/accounts/slack/login/callback/`
   - Custom adapter (`CustomSocialAccountAdapter`) syncs profile data:
     - `first_name` from Slack's `given_name`
     - `last_name` from Slack's `family_name`
     - `avatar_url` from Slack's `picture` (192px)
   - Auto-creates account if doesn't exist (`SOCIALACCOUNT_AUTO_SIGNUP = True`)

**Session Management:**
- Django's default session backend (database)
- Session expires on browser close (default)
- Session data stored in django_session table
- Logout clears session via `/accounts/logout/`

**Password Handling:**
- Django's default PBKDF2 algorithm
- Password requirements: None enforced (rely on django-allauth defaults)
- Password reset: DISABLED (no SMTP configured)

**Environment Configuration:**
```python
ALLAUTH_SLACK_CLIENT_ID=<slack-client-id>
ALLAUTH_SLACK_CLIENT_SECRET=<slack-client-secret>
```

**OAuth Scopes:**
- `openid` - User identity
- `profile` - Name and avatar
- `email` - Email address

### Protected Views

**Protection Mechanism:** `@login_required` decorator or `LoginRequiredMixin`

**Protected Views:**
- All rating/voting views (SwipeRatingView, rate_api, rate_view)
- Profile view, comparison views
- Add item view, category detail actions
- Statistics pages (partially - some data hidden when logged out)

**Public Views:**
- Home page (with limited data for logged-out users)
- Login, register, OAuth callback pages

**Permission Patterns:**
- Most views require authentication (team-based app)
- No role-based permissions (all authenticated users have equal access)
- User can only rate once per item (enforced by database constraint)
- Privacy protection: Full names shown to logged-in users, abbreviated to logged-out users

**CSRF Protection:**
- Enabled globally via `CsrfViewMiddleware`
- CSRF token required for all POST requests
- AJAX requests include CSRF token from cookie
- Trusted origins configured for production domain

---

## Development Workflow

### Version Control

**Branching Model:** Simple main-branch workflow (trunk-based)

**Commit Guidelines:**
- **When to commit:** After successfully implementing a feature or fix
- **Commit immediately:** Don't wait for multiple changes to accumulate
- **Always commit successful modifications** to ensure work is tracked and deployed

**Commit Message Format:**
```
Brief summary (50 chars or less)

- Detailed explanation point 1
- Detailed explanation point 2
- Why this change was needed

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

**Best Practices:**
- Use imperative mood: "Add feature" not "Added feature"
- Explain WHY, not just WHAT
- Reference issue numbers if applicable
- Keep commits focused on single logical change

**Do NOT Commit:**
- Sensitive data (.env, credentials, API keys)
- Generated files in .gitignore (staticfiles/, __pycache__, db.sqlite3)
- Incomplete or broken changes
- Debug code or temporary test files
- .pid file (process tracking)

**Git Workflow:**
```bash
# Check status
git status

# Review changes
git diff

# Stage changes
git add <files>

# Commit
git commit -m "Message"

# Before making changes, check for remote updates
git fetch origin
git status  # Shows if behind remote

# If behind remote, prompt user to pull
git pull origin main
```

### Database Migrations

**Migration Tool:** Django's built-in migration system

**Creating Migrations:**
```bash
# After modifying models
uv run python manage.py makemigrations

# With description
uv run python manage.py makemigrations --name add_avatar_field

# Check migration SQL (dry run)
uv run python manage.py sqlmigrate accounts 0002
```

**Applying Migrations:**
```bash
# Development
uv run python manage.py migrate

# Production (via Makefile)
make deploy  # Runs migrations automatically

# Check migration status
uv run python manage.py showmigrations
```

**Migration Best Practices:**
- Always test migrations on copy of production data
- Keep migrations small and focused
- Never edit applied migrations (create new one to modify)
- Migrations should be reversible when possible
- Document complex data migrations with comments

**Rollback Process:**
```bash
# Rollback to specific migration
uv run python manage.py migrate accounts 0001

# Rollback all migrations for app
uv run python manage.py migrate accounts zero
```

**Database Permissions:**
SQLite requires write access to both file and directory:
```bash
# If "readonly database" error occurs
sudo chown roy:roy /workspace/db.sqlite3
chmod 664 /workspace/db.sqlite3
```

### Debugging & Logging

**Logging Configuration:**
- Logs written to `/tmp/popquiz.log` for debugging
- Django's default logging to stderr (captured by nohup)
- Log format: timestamp, level, message

**Debug Mode:**
- Controlled by `DEBUG` environment variable
- Default: `True` (development)
- Production: Set to `False` for security

**Viewing Logs:**
```bash
# Recent logs
make logs

# Follow logs in real-time
make logs-follow

# Direct tail
tail -f /tmp/popquiz.log
```

**Debugging Tips:**
- Check logs first: `make logs`
- Verify server status: `make status`
- Check for Python errors in log output
- Review IMDB scraping: may fail if HTML structure changes
- Database issues: Check permissions with `ls -la db.sqlite3`

**Common Issues:**
- **Static files 404:** Run `make deploy` to collect static files
- **CSRF errors:** Check CSRF_TRUSTED_ORIGINS includes production domain
- **Database locked:** Check for stale connections, restart server
- **IMDB scraping fails:** Check imdb_utils.py regex patterns

### Serving the Application

**Development:**
```bash
# Manual start
uv run python manage.py runserver 0.0.0.0:8000

# Access at
http://localhost:8000
```

**Production Deployment:**
The application runs in a containerized production environment.

**Deployment Commands (via Makefile):**
```bash
# Full deployment
make deploy      # Migrate, collectstatic, start in background

# Process management
make start       # Start server in background
make stop        # Stop server
make restart     # Restart server
make status      # Check if running

# Monitoring
make logs        # View recent logs
make logs-follow # Tail logs in real-time
```

**Deployment Process:**
1. Check for pending migrations: `showmigrations`
2. Apply migrations: `migrate`
3. Collect static files: `collectstatic --noinput`
4. Start server in background: `nohup runserver 0.0.0.0:8000`
5. Track process ID in `.pid` file
6. Verify server started successfully

**Background Execution:**
- Uses `nohup` to detach from terminal session
- Process ID stored in `.pid` file (gitignored)
- Logs written to `/tmp/popquiz.log`
- Server persists across SSH disconnections
- Accessible at https://popquiz.rrchnm.org (SSL via reverse proxy)

**Health Checks:**
```bash
# Check server status
make status

# If not running, restart
make restart

# View recent errors
make logs
```

**Static Files (WhiteNoise):**
- Collected to `/staticfiles/` directory
- Served by WhiteNoise middleware
- Cache-busting hashes in production
- Gzip compression enabled
- No separate web server needed

### Testing Approach

**Current Status:** No automated tests implemented

**Manual Testing Focus:**
- Rating submission and updating
- IMDB data fetching with various URL formats
- Ranking calculations with edge cases
- Mobile responsive behavior
- Profile sorting options
- User comparison accuracy

**Testing Checklist:**
- [ ] Vote submission via swipe interface
- [ ] Vote updates persist correctly
- [ ] IMDB URLs parse correctly (ID extraction)
- [ ] Movie metadata fetched and cleaned
- [ ] Rankings calculate correctly (simple average)
- [ ] Mobile layout works on small screens
- [ ] Profile sorts work for all options
- [ ] User comparison shows correct overlap
- [ ] Slack OAuth login flow completes
- [ ] Static files load correctly

**Future Testing Considerations:**
- Unit tests for ranking algorithms
- IMDB scraping tests (mocked responses)
- Integration tests for voting flow
- E2E tests for critical user journeys

---

## Best Practices & Key Conventions

**Code Style:**
- **Linter:** None configured (rely on Python standards)
- **Formatter:** None configured (manual formatting)
- **Style Guide:** PEP 8 for Python

**Naming Conventions:**
- **Files:** snake_case for Python modules
- **Variables:** snake_case for local variables
- **Constants:** UPPER_CASE for settings and constants
- **Functions:** snake_case, descriptive verb phrases
- **Classes:** PascalCase for models and views
- **Templates:** snake_case.html
- **URLs:** kebab-case in URL patterns

**Django Patterns:**
- Keep business logic in views or separate utility modules
- Use Django ORM for all database access (no raw SQL)
- Templates inherit from `base.html` for consistent navigation
- Use `{% url %}` tags instead of hardcoded URLs
- Annotate querysets for aggregations instead of Python loops
- Use `select_related()` and `prefetch_related()` to avoid N+1 queries

**Frontend Patterns:**
- Vanilla JavaScript (no frameworks)
- Fetch API for AJAX requests
- Include CSRF token in POST requests
- Tailwind CSS utility classes (no custom CSS)
- Mobile-first responsive design (md: breakpoints)
- Emoji sizing: text-lg to text-4xl for visibility

**IMDB Scraping:**
- Uses regex parsing of HTML (no official API)
- Prioritizes English titles from `og:title` meta tag
- Strips metadata: ratings, genres, years in parentheses
- Handles HTML entity decoding (e.g., &amp; → &)
- 0.5s delay between requests to avoid rate limiting
- May break if IMDB changes HTML structure

**Rating Scale Convention:**
- Consistent order: Hated (left) → Disliked → Okay → Liked → Loved (right)
- Matches natural expectation (negative on left, positive on right)
- Emoji sizing: text-lg to text-4xl depending on context
- Use `inline-flex items-center gap-1 leading-none` to prevent misalignment

**Error Handling:**
- Show user-friendly messages for errors
- Log detailed errors to `/tmp/popquiz.log`
- Validate user input before database operations
- Handle IMDB scraping failures gracefully
- Check database permissions on startup

**Performance:**
- Use `.select_related()` for foreign keys
- Use `.annotate()` for aggregations
- Minimize database queries in templates
- Cache static files with WhiteNoise
- Keep queries optimized (check query count in DEBUG mode)

**Security:**
- Never commit secrets or credentials
- Validate all user input
- Use CSRF protection on forms
- Don't expose sensitive data to logged-out users
- Hash passwords (Django default PBKDF2)

---

## Notes for AI Agents

**Preferred Approaches:**
- Use Django ORM instead of raw SQL
- Keep views focused (single responsibility)
- Extract complex logic to utility modules
- Follow existing patterns in similar views
- Prefer annotation/aggregation over Python loops
- Use template tags for reusable template logic

**Important Context:**
- This is a **production environment** at https://popquiz.rrchnm.org
- The database file must be owned by user "roy" (see Database Permissions section)
- IMDB scraping is fragile - HTML structure changes will break it
- No email functionality (SMTP disabled) - don't suggest email features
- Rating scale changed from 3-point (yes/meh/no) to 5-point in commit 8600dad071
- The user is non-technical - avoid prompting about architecture, deployment, databases

**When Making Changes:**
1. **Understand** - Read relevant code and documentation
2. **Implement** - Make the necessary changes
3. **Test** - Verify changes work (restart server if needed)
4. **Commit** - Always commit successful modifications

**Deployment Workflow:**
1. Fetch remote changes: `git fetch origin`
2. Prompt user to pull if behind remote
3. Make and test changes
4. Commit changes with descriptive message
5. Deploy: `make deploy`
6. Verify: `make status && make logs`

**What to Avoid:**
- Don't add complex authentication logic (Slack OAuth is sufficient)
- Don't suggest adding email features (SMTP disabled)
- Don't modify staticfiles/ directly (generated by collectstatic)
- Don't use JavaScript frameworks (vanilla JS only)
- Don't ask user technical questions (deployment, architecture, database design)
- Don't create documentation files unless requested
- Don't use emojis unless explicitly requested

**File Modification Guidelines:**
- Always read files before editing
- Maintain consistent formatting
- Update related files (views, templates, URLs together)
- Test changes before committing
- Use descriptive commit messages

**IMDB Scraping Gotchas:**
- Variable name conflict: use `page_html` not `html` (avoids module conflict)
- Title metadata: strip ratings (⭐), genres (|), years in parens
- Use `html.unescape()` for HTML entities
- Prioritize `og:title` for English titles
- Genre limit: max 3 genres to keep concise

**Static Files:**
- Source: `/workspace/static/` (manually added files only)
- Generated: `/workspace/staticfiles/` (collectstatic output)
- WhiteNoise serves from staticfiles/ with cache-busting
- Warning about missing `/workspace/static/` is expected and harmless

**Database Permissions:**
If you see "attempt to write a readonly database":
```bash
sudo chown roy:roy /workspace/db.sqlite3
chmod 664 /workspace/db.sqlite3
make restart
```

**Testing Checklist:**
- After code changes, verify server restarts successfully
- Check logs for errors: `make logs`
- Test the feature in browser (mobile and desktop)
- Ensure no database permission issues
- Verify static files load correctly

**Common Pitfalls:**
- Forgetting to restart server after model changes
- Not running migrations after model modifications
- CSRF token missing in AJAX POST requests
- Database file ownership issues
- IMDB HTML structure changes breaking scraper
- Mobile layout issues (test on small screens)
- Emoji alignment issues (use inline-flex and leading-none)

---

*Last Updated: 2026-02-17*
*This document is maintained for AI agent context and developer onboarding.*

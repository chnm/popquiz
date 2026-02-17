# PopQuiz Deployment Specification

This document outlines the deployment configuration and operational requirements for PopQuiz in production.

## Environment

**Hosting URL**: https://popquiz.rrchnm.org

**Container Environment**: This application runs in a containerized environment where:
- SSL/TLS termination is handled by reverse proxy (outside this container)
- Application serves on `0.0.0.0:8000` internally
- All external traffic is routed through reverse proxy

## Technology Stack

- **Framework**: Django 5.2+ (latest stable)
- **Database**: SQLite (db.sqlite3)
- **Static Files**: WhiteNoise (for production static file serving)
- **Package Manager**: uv (for Python version and dependency management)
- **Authentication**: django-allauth with Slack OAuth integration

## Environment Variables

The following environment variables are configured:

- `ALLAUTH_SLACK_CLIENT_ID`: Slack OAuth client ID for user authentication
- `ALLAUTH_SLACK_CLIENT_SECRET`: Slack OAuth client secret

**Note**: Email confirmations and SMTP are intentionally disabled for this deployment.

## Deployment Process

The deployment process is automated via `Makefile`. Key steps include:

1. **Check & apply migrations**: Ensure database schema is up-to-date
2. **Collect static files**: Gather all static assets for WhiteNoise serving
3. **Background deployment**: Start server using nohup to detach from session
4. **Process tracking**: Maintain .pid file for process management across sessions

### Pre-Deployment Checklist

Before deploying:
- [ ] All changes committed to git
- [ ] Fetched latest from remote repository
- [ ] Dependencies updated in pyproject.toml (if needed)
- [ ] Database migrations created (if schema changed)

### Deployment Commands

```bash
# Deploy the application (full process)
make deploy

# Check if app is running
make status

# Stop the application
make stop

# Restart the application
make restart

# View server logs
make logs

# Tail server logs in real-time
make logs-follow
```

## Process Management

### Background Server

The Django application runs in the background using `nohup` to ensure it persists across terminal sessions:

```bash
nohup uv run python manage.py runserver 0.0.0.0:8000 > /tmp/popquiz.log 2>&1 &
```

**Benefits:**
- Server continues running after terminal disconnection
- Not tied to any specific shell session
- Allows for remote deployments without persistent SSH connection

### PID File Tracking

A `.pid` file stores the process ID of the running server:
- **Location**: `/workspace/.pid`
- **Purpose**: Track server process across sessions for stop/restart operations
- **Git**: Excluded via .gitignore (not tracked in version control)

The Makefile automatically manages this file during start/stop operations.

## Logging

All application logs are written to `/tmp/` for debugging and monitoring:

- **Server Output**: `/tmp/popquiz.log` (stdout and stderr)
- **Django Logs**: Configured in settings.py to write to /tmp
- **Log Rotation**: Container environment handles log rotation externally

**Why /tmp?**
- Accessible for debugging without affecting repository
- Container-friendly location
- Easy to tail for real-time monitoring

## Static Files

WhiteNoise is configured for production-ready static file serving:

1. **Collection**: `python manage.py collectstatic --noinput`
   - Gathers all static files to `/staticfiles/` directory
   - Includes cache-busting hashes for browser caching

2. **Serving**: WhiteNoise middleware serves files directly from Django
   - No need for nginx or separate static file server
   - Automatic gzip compression
   - Far-future cache headers for optimal performance

3. **Location**:
   - Source files: `/static/` (tracked in git for select files like founder images)
   - Collected files: `/staticfiles/` (generated, not tracked in git)

## Database

SQLite database (`db.sqlite3`) is used for this deployment:

- **Migrations**: Applied automatically during deployment
- **Backup**: Handled externally (outside this container)
- **Location**: `/workspace/db.sqlite3`

**Note**: Database file is not tracked in git (.gitignore).

## Health Monitoring

The Makefile provides commands to check server health:

```bash
# Check if process is running
make status

# View recent logs
make logs

# Monitor logs in real-time
make logs-follow
```

The deployment system automatically checks if the server is running and restarts it if needed during deployments.

## Git Workflow

### Version Control

All code changes are committed to the local git repository with meaningful commit messages:

```bash
# Check status
git status

# Stage changes
git add <files>

# Commit with message
git commit -m "Brief summary

Detailed explanation

Co-Authored-By: Claude <noreply@anthropic.com>"
```

### Remote Synchronization

Before making changes, always check for remote updates:

```bash
# Fetch from remote
git fetch origin

# Check status (shows if behind remote)
git status

# Pull if needed
git pull origin main
```

**User Prompting**: If remote changes are detected, prompt the user to pull before proceeding with new work.

## Security Considerations

- **Secrets**: Never commit secrets to git (use environment variables)
- **SMTP**: Email functionality intentionally disabled (no email confirmations)
- **Authentication**: Slack OAuth only (no password authentication needed)
- **SSL/TLS**: Handled by reverse proxy (not in this container)

## Performance

- **WhiteNoise**: Optimized static file serving with compression and caching
- **SQLite**: Sufficient for team-size usage (consider PostgreSQL for larger scale)
- **Static Files**: Cache-busting ensures fresh content after updates

## Troubleshooting

### Server Not Running

```bash
# Check status
make status

# View logs for errors
make logs

# Restart server
make restart
```

### Port Already in Use

If port 8000 is occupied:
```bash
# Find process on port 8000
lsof -ti:8000

# Kill the process
kill $(lsof -ti:8000)

# Restart via Makefile
make restart
```

### Static Files Not Loading

```bash
# Re-collect static files
uv run python manage.py collectstatic --noinput

# Check WhiteNoise configuration in settings.py
```

### Database Issues

```bash
# Check pending migrations
uv run python manage.py showmigrations

# Apply migrations
uv run python manage.py migrate

# Check database integrity
uv run python manage.py check

# Fix database permissions if getting "readonly database" error
sudo chown roy:roy /workspace/db.sqlite3
chmod 664 /workspace/db.sqlite3
```

### Database Permissions

SQLite requires write access to both the database file and its directory:
- Database file should be owned by the user running the server
- File permissions should be 664 (rw-rw-r--)
- Directory must be writable for journal files (.sqlite3-journal)

If you see "attempt to write a readonly database" errors:
1. Check file ownership: `ls -la /workspace/db.sqlite3`
2. Fix ownership: `sudo chown roy:roy /workspace/db.sqlite3`
3. Ensure writable: `chmod 664 /workspace/db.sqlite3`
4. Restart server: `make restart`

---

*Last Updated: 2026-02-17*
*This specification is maintained for deployment and operations reference.*

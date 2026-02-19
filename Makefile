.PHONY: help deploy start stop restart status logs logs-follow clean migrate collectstatic check

# Default target - show help
help:
	@echo "PopQuiz Deployment Makefile"
	@echo "============================"
	@echo ""
	@echo "Available targets:"
	@echo "  make deploy       - Full deployment (migrate, collectstatic, start server)"
	@echo "  make start        - Start Nginx + Gunicorn in background"
	@echo "  make stop         - Stop Nginx + Gunicorn"
	@echo "  make restart      - Restart Nginx + Gunicorn"
	@echo "  make status       - Check if server is running"
	@echo "  make logs         - View recent server logs"
	@echo "  make logs-follow  - Tail server logs in real-time"
	@echo "  make migrate      - Run database migrations"
	@echo "  make collectstatic - Collect static files"
	@echo "  make check        - Run Django system checks"
	@echo "  make clean        - Clean up log files"
	@echo ""
	@echo "Production URL: https://popquiz.rrchnm.org"
	@echo "Nginx: port 8000 (static/media direct, app proxied to 8001)"
	@echo "Gunicorn: 127.0.0.1:8001"
	@echo "Logs: /tmp/popquiz.log"
	@echo "PID file: .pid"

# Full deployment process
deploy: check migrate collectstatic
	@echo "==> Starting deployment..."
	@$(MAKE) stop 2>/dev/null || true
	@$(MAKE) start
	@sleep 2
	@$(MAKE) status
	@echo "==> Deployment complete!"
	@echo "==> View logs with: make logs"

# Run database migrations
migrate:
	@echo "==> Checking for pending migrations..."
	@uv run python manage.py showmigrations | grep '\[ \]' && echo "Pending migrations found" || echo "No pending migrations"
	@echo "==> Running migrations..."
	@uv run python manage.py migrate

# Collect static files
collectstatic:
	@echo "==> Collecting static files..."
	@uv run python manage.py collectstatic --noinput

# Run Django system checks
check:
	@echo "==> Running Django system checks..."
	@uv run python manage.py check

# Start Gunicorn + Nginx
start:
	@if [ -f .pid ] && kill -0 $$(cat .pid) 2>/dev/null; then \
		echo "==> Server is already running (PID: $$(cat .pid))"; \
		exit 1; \
	fi
	@echo "==> Starting Gunicorn on 127.0.0.1:8001..."
	@nohup uv run gunicorn popquiz.wsgi:application \
		--bind 127.0.0.1:8001 \
		--workers 4 \
		--timeout 120 \
		--access-logfile /tmp/popquiz.log \
		--error-logfile /tmp/popquiz.log \
		> /tmp/popquiz.log 2>&1 & echo $$! > .pid
	@sleep 2
	@if [ -f .pid ] && kill -0 $$(cat .pid) 2>/dev/null; then \
		echo "==> Gunicorn started (PID: $$(cat .pid))"; \
	else \
		echo "==> ERROR: Gunicorn failed to start. Check logs with: make logs"; \
		exit 1; \
	fi
	@echo "==> Starting Nginx on port 8000..."
	@sudo nginx -s quit 2>/dev/null || true
	@sleep 1
	@sudo nginx
	@echo "==> Nginx started"

# Stop Gunicorn + Nginx
stop:
	@echo "==> Stopping Nginx..."
	@sudo nginx -s quit 2>/dev/null || true
	@if [ ! -f .pid ]; then \
		echo "==> No PID file found. Gunicorn may not be running."; \
	elif kill -0 $$(cat .pid) 2>/dev/null; then \
		echo "==> Stopping Gunicorn (PID: $$(cat .pid))..."; \
		kill $$(cat .pid); \
		rm -f .pid; \
		echo "==> Gunicorn stopped"; \
	else \
		echo "==> Gunicorn is not running (stale PID file removed)"; \
		rm -f .pid; \
	fi

# Restart
restart: stop
	@sleep 2
	@$(MAKE) start

# Check server status
status:
	@if [ -f .pid ] && kill -0 $$(cat .pid) 2>/dev/null; then \
		echo "==> Gunicorn is RUNNING (PID: $$(cat .pid))"; \
		echo "==> Public URL: https://popquiz.rrchnm.org"; \
	else \
		echo "==> Gunicorn is NOT RUNNING"; \
	fi
	@if sudo nginx -t 2>/dev/null && pgrep -x nginx > /dev/null 2>&1; then \
		echo "==> Nginx is RUNNING"; \
	else \
		echo "==> Nginx is NOT RUNNING"; \
	fi

# View recent logs
logs:
	@if [ -f /tmp/popquiz.log ]; then \
		echo "==> Recent server logs (/tmp/popquiz.log):"; \
		echo ""; \
		tail -n 50 /tmp/popquiz.log; \
	else \
		echo "==> No log file found at /tmp/popquiz.log"; \
	fi

# Tail logs in real-time
logs-follow:
	@echo "==> Tailing server logs (Ctrl+C to exit)..."
	@tail -f /tmp/popquiz.log

# Clean up log files
clean:
	@echo "==> Cleaning up log files..."
	@rm -f /tmp/popquiz.log
	@echo "==> Log files cleaned"

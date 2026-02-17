.PHONY: help deploy start stop restart status logs logs-follow clean migrate collectstatic check

# Default target - show help
help:
	@echo "PopQuiz Deployment Makefile"
	@echo "============================"
	@echo ""
	@echo "Available targets:"
	@echo "  make deploy       - Full deployment (migrate, collectstatic, start server)"
	@echo "  make start        - Start the Django server in background"
	@echo "  make stop         - Stop the running Django server"
	@echo "  make restart      - Restart the Django server"
	@echo "  make status       - Check if server is running"
	@echo "  make logs         - View recent server logs"
	@echo "  make logs-follow  - Tail server logs in real-time"
	@echo "  make migrate      - Run database migrations"
	@echo "  make collectstatic - Collect static files"
	@echo "  make check        - Run Django system checks"
	@echo "  make clean        - Clean up log files"
	@echo ""
	@echo "Production URL: https://popquiz.rrchnm.org"
	@echo "Server binds to: 0.0.0.0:8000"
	@echo "Logs location: /tmp/popquiz.log"
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

# Start the server in background
start:
	@if [ -f .pid ] && kill -0 $$(cat .pid) 2>/dev/null; then \
		echo "==> Server is already running (PID: $$(cat .pid))"; \
		exit 1; \
	fi
	@echo "==> Starting Django server in background..."
	@nohup uv run python manage.py runserver 0.0.0.0:8000 > /tmp/popquiz.log 2>&1 & echo $$! > .pid
	@sleep 1
	@if [ -f .pid ] && kill -0 $$(cat .pid) 2>/dev/null; then \
		echo "==> Server started successfully (PID: $$(cat .pid))"; \
	else \
		echo "==> ERROR: Server failed to start. Check logs with: make logs"; \
		exit 1; \
	fi

# Stop the server
stop:
	@if [ ! -f .pid ]; then \
		echo "==> No PID file found. Server may not be running."; \
		exit 0; \
	fi
	@if kill -0 $$(cat .pid) 2>/dev/null; then \
		echo "==> Stopping Django server (PID: $$(cat .pid))..."; \
		kill $$(cat .pid); \
		rm -f .pid; \
		echo "==> Server stopped successfully"; \
	else \
		echo "==> Server is not running (stale PID file removed)"; \
		rm -f .pid; \
	fi

# Restart the server
restart: stop
	@sleep 2
	@$(MAKE) start

# Check server status
status:
	@if [ -f .pid ]; then \
		if kill -0 $$(cat .pid) 2>/dev/null; then \
			echo "==> Server is RUNNING (PID: $$(cat .pid))"; \
			echo "==> Listening on: 0.0.0.0:8000"; \
			echo "==> Public URL: https://popquiz.rrchnm.org"; \
			exit 0; \
		else \
			echo "==> Server is NOT RUNNING (stale PID file exists)"; \
			exit 1; \
		fi \
	else \
		echo "==> Server is NOT RUNNING (no PID file found)"; \
		exit 1; \
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

.PHONY: up down build logs seed test lint clean

# Start all services
up:
	docker compose up -d --build

# Stop all services
down:
	docker compose down

# Rebuild images
build:
	docker compose build --no-cache

# View logs
logs:
	docker compose logs -f

# View specific service logs
logs-%:
	docker compose logs -f $*

# Seed URLs for crawling
seed:
	docker compose exec api python -m scripts.seed $(URLS)

# Run tests
test:
	docker compose exec api pytest tests/ -v

# Lint
lint:
	docker compose exec api python -m py_compile crawldb/config.py

# Clean volumes (DESTRUCTIVE)
clean:
	docker compose down -v
	docker system prune -f

# Status
status:
	docker compose ps

# Shell into api container
shell:
	docker compose exec api bash

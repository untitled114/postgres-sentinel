.PHONY: up down build reset test lint fmt chaos-random validate status logs shell-db seed

up:
	docker compose up -d

down:
	docker compose down

build:
	docker compose build --no-cache

reset:
	docker compose down -v
	docker compose up -d --build

test:
	pytest tests/ -v --cov=sentinel --cov-report=term-missing

lint:
	flake8 sentinel/ tests/ --max-line-length=100 --ignore=E203,W503
	isort --check-only sentinel/ tests/
	black --check sentinel/ tests/

fmt:
	isort sentinel/ tests/
	black sentinel/ tests/

chaos-random:
	curl -s -X POST http://localhost:8000/api/chaos/random | python3 -m json.tool

validate:
	curl -s -X POST http://localhost:8000/api/validation/run | python3 -m json.tool

status:
	curl -s http://localhost:8000/api/health | python3 -m json.tool

logs:
	docker compose logs -f sentinel

shell-db:
	docker compose exec postgres psql -U sentinel -d sentinel

seed:
	docker compose exec postgres psql -U sentinel -d sentinel -f /docker-entrypoint-initdb.d/08_seed_initial_data.sql

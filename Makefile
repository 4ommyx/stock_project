#Commands
help:
	@echo "Usage:"
	@echo "  make build       - Build Docker image"
	@echo "  make up          - Start all containers in background"
	@echo "  make up-prod     - Start all containers in background (Production)"
	@echo "  make down        - Stop all containers"
	@echo "  make down-prod   - Stop all containers in (Production)"
	@echo "  make restart     - Restart all containers"
	@echo "  make logs        - Show logs for all containers"

up:
	docker-compose up -d

up-prod:
	sudo docker compose -f docker-compose.prod.yml up -d --build

down:
	docker-compose down

down-prod:
	sudo docker compose -f docker-compose.prod.yml down

build:
	docker-compose build

restart:
	docker-compose down && docker-compose up -d

logs:
	docker-compose logs -f analytic-ml-dev
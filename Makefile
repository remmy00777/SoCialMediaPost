SHELL := /bin/bash
.PHONY: install setup dev start stop restart status doctor test lint typecheck backup restore clean demo logs sbom audit
install:
	./scripts/install.sh
setup:
	./scripts/install.sh --no-start
dev:
	cd backend && PYTHONPATH=. uvicorn app.main:app --reload --host 127.0.0.1 --port 8765
start:
	./scripts/start.sh
stop:
	./scripts/stop.sh
restart:
	./scripts/restart.sh
status:
	./scripts/status.sh
doctor:
	./scripts/doctor.sh
test:
	cd backend && PYTHONPATH=. pytest
lint:
	cd backend && ruff check app tests
	cd frontend && npm run lint
typecheck:
	cd backend && mypy app
	cd frontend && npm run typecheck
backup:
	./scripts/backup.sh
restore:
	@test -n "$(FILE)" || (echo "Use make restore FILE=/path/to/backup.tar.gz"; exit 1)
	./scripts/restore.sh "$(FILE)"
demo:
	./scripts/demo.sh
logs:
	docker compose logs -f --tail=150 api worker beat
sbom:
	./scripts/generate-sbom.sh
audit:
	./scripts/security-scan.sh
clean:
	docker compose down --remove-orphans
	find . -type d \( -name __pycache__ -o -name .pytest_cache -o -name .mypy_cache -o -name .ruff_cache \) -prune -exec rm -rf {} +

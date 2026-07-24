
ifneq ($(shell which docker-compose 2>/dev/null),)
    DOCKER_COMPOSE := docker-compose
else
    DOCKER_COMPOSE := docker compose
endif

install:
	$(DOCKER_COMPOSE) up -d

remove:
	@chmod +x confirm_remove.sh
	@./confirm_remove.sh

start:
	$(DOCKER_COMPOSE) start
startAndBuild: 
	$(DOCKER_COMPOSE) up -d --build

stop:
	$(DOCKER_COMPOSE) stop

update:
	# Calls the LLM update script
	chmod +x update_ollama_models.sh
	@./update_ollama_models.sh
	@git pull
	$(DOCKER_COMPOSE) down
	# Make sure the bcgpt container is stopped before rebuilding
	@docker stop bcgpt || true
	$(DOCKER_COMPOSE) up --build -d
	$(DOCKER_COMPOSE) start

# =============================================================================
# Testing
# =============================================================================
# Canonical commands per docs/CONTINUOUS_IMPROVEMENT_REVIEW_2026-06-23.md §3.7.
# Run from repo root: `make test-backend-unit` etc.

# Backend unit tests — 564 standalone tests, no Docker required.
test-backend-unit:
	cd backend && python -m pytest bcgpt/test/unit -q

# Backend integration tests — collection only (actual run needs Docker/Postgres).
# Use this as the collection gate; full run is docker-dependent (see PRODUCTION_HARDENING_LOG Iteration 3).
test-backend-integration-collect:
	cd backend && python -m pytest bcgpt/test/apps --collect-only -q

# Backend integration tests — full run (requires Docker/testcontainers for Postgres).
test-backend-integration: test-backend-integration-collect
	cd backend && python -m pytest bcgpt/test/apps -q

# All backend tests: unit + integration.
test-backend: test-backend-unit test-backend-integration

# Frontend tests (bun-powered vitest).
test-frontend:
	bun run test:frontend

# Everything: backend unit + frontend.
test: test-backend-unit test-frontend

# Lint/typecheck (non-blocking, for local dev reference).
lint-frontend:
	bunx eslint .

typecheck-frontend:
	bun run check

# Svelte-check ratchet gate — fails if error count increased vs baseline.
# Update baseline after fixing errors: `python scripts/check_ratchet.py --update`
check-frontend-ratchet:
	python scripts/check_ratchet.py

# Direct fetch ratchet gate — fails if new fetch() calls bypass ApiClient.
# Update allowlist: `python scripts/check_direct_fetch.py --update`
check-direct-fetch:
	python scripts/check_direct_fetch.py

# =============================================================================
# Route authorization inventory
# =============================================================================
# Regenerate docs/generated/ROUTE_AUTHORIZATION_INVENTORY.md from AST scan.
# See docs/ACCESS_CONTROL_ADMIN_GOVERNANCE_PLAN_2026-06-23.md Phase 0.
route-auth-inventory:
	python scripts/extract_route_authorization.py

# =============================================================================
# Config inventory
# =============================================================================
# Regenerate docs/generated/CONFIG_INVENTORY.md and CONFIG_INVENTORY_DIFF.md
# from source AST scan. See docs/CONFIG_INVENTORY_GENERATION_RUNBOOK_2026-06-23.md.
# Extractor version pinned in scripts/extract_config_inventory.py.
config-inventory:
	python scripts/extract_config_inventory.py


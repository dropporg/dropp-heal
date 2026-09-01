venv := "./venv/bin"
src := "main.py worker.py api tests"

# List available recipes.
default:
    @just --list

# Run the api service with reload.
run:
    {{venv}}/fastapi dev main.py

# Run the monitoring worker with reload.
run-worker:
    {{venv}}/fastapi dev worker.py --port 8001

# Sort imports.
isort:
    {{venv}}/isort --profile black {{src}}

# Format code.
black:
    {{venv}}/black {{src}}

# Sort imports, then format.
format: isort black

# Report formatting problems without editing files.
check:
    {{venv}}/isort --profile black --check-only --diff {{src}}
    {{venv}}/black --check --diff {{src}}

# Lint, exactly as CI does.
lint:
    {{venv}}/ruff check .

# Apply the lint fixes ruff can make safely.
lint-fix:
    {{venv}}/ruff check --fix .

# Scan our code and our dependencies, exactly as CI does.
audit:
    {{venv}}/bandit -q -r api main.py worker.py
    {{venv}}/pip-audit -r requirements.txt --progress-spinner off

# Scan the history and working tree for committed secrets. Needs gitleaks:
# nix-shell -p gitleaks --run "just secrets"
secrets:
    gitleaks git . --redact --no-banner
    gitleaks dir . --redact --no-banner

# Run the test suite.
test *args:
    {{venv}}/python -m pytest {{args}}

# Start the local mysql and influxdb containers.
infra-up:
    docker compose -f docker-compose.infra.yml up -d

# Stop them, keeping the data volumes.
infra-down:
    docker compose -f docker-compose.infra.yml down

# Build every component image.
docker-build:
    docker build -f deployments/docker/Dockerfile.api -t heal-api:latest .
    docker build -f deployments/docker/Dockerfile.worker -t heal-worker:latest .
    docker build -f deployments/docker/Dockerfile.migrate -t heal-migrate:latest .
    docker build -f deployments/docker/Dockerfile.dashboard -t heal-dashboard:latest .

# Run the dashboard with reload.
run-dashboard:
    cd dashboard && npm run dev

# Lint and render the chart. Chart.yaml carries version placeholders that helm
# rejects, so this stamps a throwaway version into a copy first.
chart-lint:
    #!/usr/bin/env bash
    set -euo pipefail
    work="$(mktemp -d)"
    trap 'rm -rf "$work"' EXIT
    cp -r deployments/chart "$work/chart"
    eval "$(.github/scripts/chart-version.sh local)"
    sed -i -e "s|__chartVersion__|$chart_version|" -e "s|__appVersion__|$app_version|" \
        "$work/chart/Chart.yaml"
    helm lint --strict "$work/chart" --set secrets.databasePassword=lint --set secrets.influxdbToken=lint
    helm template heal "$work/chart" --set secrets.databasePassword=x --set secrets.influxdbToken=y >/dev/null
    echo "rendered ok at chart $chart_version, app $app_version"

# Apply all pending migrations.
upgrade:
    {{venv}}/alembic upgrade head

# Roll back one migration.
downgrade:
    {{venv}}/alembic downgrade -1

# Autogenerate a revision from the models: just revision "add sites"
revision message:
    {{venv}}/alembic revision --autogenerate -m "{{message}}"

# Show the currently applied revision.
current:
    {{venv}}/alembic current

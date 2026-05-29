#!/usr/bin/env bash
set -euo pipefail

TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-180}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

get_env_value() {
  local key="$1"
  local default="$2"
  if [[ ! -f .env ]]; then
    printf '%s' "$default"
    return
  fi
  local line
  line="$(grep -E "^[[:space:]]*${key}[[:space:]]*=" .env | head -n 1 || true)"
  if [[ -z "$line" ]]; then
    printf '%s' "$default"
    return
  fi
  local value="${line#*=}"
  value="${value%\"}"
  value="${value#\"}"
  value="${value%\'}"
  value="${value#\'}"
  printf '%s' "$value"
}

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker CLI not found. Please install Docker first."
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "Docker daemon is not running. Start Docker and retry."
  exit 1
fi

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "[init] .env not found. Copied .env.example -> .env"
fi

API_PORT="$(get_env_value API_PORT 8000)"
WEB_PORT="$(get_env_value WEB_PORT 5173)"
HEALTH_URL="http://127.0.0.1:${API_PORT}/healthz"

COMPOSE_ARGS=(-f infra/docker-compose.yml --env-file .env)
docker compose "${COMPOSE_ARGS[@]}" up -d --build

start_ts="$(date +%s)"
while true; do
  if curl -fsS "$HEALTH_URL" >/dev/null 2>&1; then
    break
  fi
  now_ts="$(date +%s)"
  if (( now_ts - start_ts >= TIMEOUT_SECONDS )); then
    echo "[error] API health check timeout: $HEALTH_URL"
    docker compose "${COMPOSE_ARGS[@]}" ps
    exit 1
  fi
  sleep 2
done

echo ""
echo "Demo is ready."
echo "Web: http://localhost:${WEB_PORT}"
echo "API Docs: http://localhost:${API_PORT}/docs"
echo ""
echo "Demo login:"
echo "visitor@example.local"
echo "tech_staff@example.local"
echo "sales_staff@example.local"
echo "product_staff@example.local"
echo "bilingual_admin@example.local"
echo ""
echo "Next checks:"
echo "python scripts/test_permission_matrix.py --base-url http://127.0.0.1:${API_PORT}"

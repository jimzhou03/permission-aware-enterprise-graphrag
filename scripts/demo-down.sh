#!/usr/bin/env bash
set -euo pipefail

RESET_VOLUMES=false
if [[ "${1:-}" == "--reset-volumes" ]]; then
  RESET_VOLUMES=true
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

COMPOSE_ARGS=(-f infra/docker-compose.yml --env-file .env down)
if [[ "$RESET_VOLUMES" == "true" ]]; then
  COMPOSE_ARGS+=(-v)
fi

docker compose "${COMPOSE_ARGS[@]}"

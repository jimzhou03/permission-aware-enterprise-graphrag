#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
WEB_URL="${WEB_URL:-http://127.0.0.1:5173}"
SKIP_PERMISSION_MATRIX="${SKIP_PERMISSION_MATRIX:-0}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "[check] API health: ${BASE_URL}/healthz"
curl -fsS "${BASE_URL}/healthz" >/dev/null
echo "  [ok] api health"

echo "[check] Web availability: ${WEB_URL}"
curl -fsS "${WEB_URL}" >/dev/null
echo "  [ok] web"

echo "[check] Compose services"
docker compose -f infra/docker-compose.yml --env-file .env ps

login_and_get_token() {
  local email="$1"
  curl -fsS -X POST "${BASE_URL}/api/v1/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"${email}\",\"password\":\"Passw0rd!123\"}" \
    | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])"
}

accounts=(
  visitor@example.local
  tech_staff@example.local
  sales_staff@example.local
  marketing_staff@example.local
  support_staff@example.local
  hr_staff@example.local
  admin_staff@example.local
  product_staff@example.local
  bilingual_admin@example.local
)

for email in "${accounts[@]}"; do
  token="$(login_and_get_token "$email")"
  if [[ -z "$token" ]]; then
    echo "[error] login failed: ${email}"
    exit 1
  fi
  echo "  [ok] login ${email}"
done

admin_token="$(login_and_get_token "bilingual_admin@example.local")"
kb_count="$(
  curl -fsS "${BASE_URL}/api/v1/knowledge-bases" \
    -H "Authorization: Bearer ${admin_token}" \
    | python -c "import sys,json; print(len(json.load(sys.stdin)))"
)"
echo "[check] Seeded KB count: ${kb_count}"
if [[ "$kb_count" != "9" ]]; then
  echo "[error] expected 9 knowledge bases, got ${kb_count}"
  exit 1
fi

if [[ "$SKIP_PERMISSION_MATRIX" != "1" ]]; then
  echo "[check] Permission matrix script"
  python scripts/test_permission_matrix.py --base-url "${BASE_URL}"
fi

echo "[done] demo-check passed."

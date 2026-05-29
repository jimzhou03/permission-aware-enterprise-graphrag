#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"

login_token="$(
  curl -fsS -X POST "${BASE_URL}/api/v1/auth/login" \
    -H "Content-Type: application/json" \
    -d '{"email":"bilingual_admin@example.local","password":"Passw0rd!123"}' \
    | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])"
)"

if [[ -z "$login_token" ]]; then
  echo "[error] login failed"
  exit 1
fi

config_json="$(
  curl -fsS "${BASE_URL}/api/v1/system/retrieval-config" \
    -H "Authorization: Bearer ${login_token}"
)"

embedding_provider="$(
  printf '%s' "$config_json" | python -c "import sys,json; print(json.load(sys.stdin)['embedding_provider'])"
)"
retrieval_engine="$(
  printf '%s' "$config_json" | python -c "import sys,json; print(json.load(sys.stdin)['retrieval_engine'])"
)"
pgvector_available="$(
  printf '%s' "$config_json" | python -c "import sys,json; print(json.load(sys.stdin)['pgvector_available'])"
)"
pgvector_sql_enabled="$(
  printf '%s' "$config_json" | python -c "import sys,json; print(json.load(sys.stdin)['pgvector_sql_retrieval_enabled'])"
)"

echo "[check] embedding_provider: ${embedding_provider}"
echo "[check] retrieval_engine: ${retrieval_engine}"
echo "[check] pgvector_available: ${pgvector_available}"
echo "[check] pgvector_sql_retrieval_enabled: ${pgvector_sql_enabled}"

if [[ "$embedding_provider" == *deterministic-mock* ]]; then
  echo "[warn] runtime is still mock embedding (or local embedding fallback to mock)."
else
  echo "[ok] non-mock embedding provider is active."
fi

ask_json="$(
  curl -fsS -X POST "${BASE_URL}/api/v1/qa/ask" \
    -H "Authorization: Bearer ${login_token}" \
    -H "Content-Type: application/json" \
    -d '{"question":"Summarize the Robot SDK Manual deployment checklist.","mode":"auto","knowledge_base_codes":[]}'
)"
denied="$(
  printf '%s' "$ask_json" | python -c "import sys,json; print(json.load(sys.stdin)['denied'])"
)"
mode="$(
  printf '%s' "$ask_json" | python -c "import sys,json; print(json.load(sys.stdin)['mode'])"
)"
sources_count="$(
  printf '%s' "$ask_json" | python -c "import sys,json; print(len(json.load(sys.stdin).get('sources', [])))"
)"

echo "[check] denied: ${denied}"
echo "[check] mode: ${mode}"
echo "[check] sources: ${sources_count}"
echo "[done] local embedding check finished."

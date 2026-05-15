#!/usr/bin/env bash
# Quick smoke check after deploy (usage: ./scripts/verify_deploy.sh [base_url])
set -euo pipefail

BASE="${1:-https://projectsiluma-production.up.railway.app}"

echo "Checking $BASE ..."
health=$(curl -fsS "$BASE/health")
echo "health: $health"

html=$(curl -fsS "$BASE/")
if echo "$html" | grep -q 'id="root"'; then
  echo "OK: SPA index detected (React root)"
else
  echo "FAIL: legacy HTML still served at /" >&2
  echo "$html" | head -8 >&2
  exit 1
fi

asset=$(echo "$html" | grep -oE '/assets/[^"]+\.js' | head -1)
if [ -z "$asset" ]; then
  echo "WARN: no asset script tag in index"
  exit 0
fi

ctype=$(curl -fsSI "$BASE$asset" | grep -i '^content-type:' || true)
echo "asset $asset -> $ctype"
if echo "$ctype" | grep -qi 'javascript'; then
  echo "OK: JS asset served"
else
  echo "FAIL: asset is not JavaScript (build may be incomplete)" >&2
  exit 1
fi

echo "All checks passed."

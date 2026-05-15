#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/frontend"

echo "==> Building frontend SPA..."
if [ -f package-lock.json ]; then
  npm ci
else
  npm install
fi
npm run build
test -f dist/index.html
echo "==> Frontend build complete"

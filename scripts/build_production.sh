#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> Installing Python dependencies..."
pip install -r requirements.txt

echo "==> Building frontend SPA..."
cd frontend
if [ -f package-lock.json ]; then
  npm ci
else
  npm install
fi
npm run build
test -f dist/index.html

echo "==> Build complete (dist/index.html ready)"

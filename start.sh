#!/usr/bin/env bash
# VerseRiver startup script
# Run this from the project root once to install and launch.
set -e

echo "🌊 VerseRiver"
echo ""

# ── Python dependencies ──────────────────────────────────
if ! python -c "import fastapi" 2>/dev/null; then
  echo "Installing Python dependencies…"
  pip install -r requirements.txt
fi

# ── Node / frontend build ────────────────────────────────
if [ ! -d frontend/dist ]; then
  echo "Building frontend…"
  cd frontend
  npm install --silent
  npm run build --silent
  cd ..
fi

# ── Seed data ────────────────────────────────────────────
if [ ! -f data/poems.db ]; then
  echo "Importing seed data…"
  python scripts/import_seeds.py
fi

# ── Launch ───────────────────────────────────────────────
echo ""
echo "Starting server at http://localhost:8000"
echo "Press Ctrl+C to stop."
echo ""
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000

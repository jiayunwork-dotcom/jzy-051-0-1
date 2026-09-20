#!/usr/bin/env sh
# Run the backend's automated test suite.
#
#   ./run-tests.sh           # local python (uses in-memory SQLite)
#   ./run-tests.sh docker    # inside docker compose against the stack
set -e

if [ "${1:-}" = "docker" ]; then
  docker compose run --rm tests
  exit 0
fi

cd "$(dirname "$0")/backend"
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
  ./.venv/bin/pip install -q -r requirements.txt
fi
./.venv/bin/python -m pytest app/tests -v

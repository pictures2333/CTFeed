#!/bin/sh
set -eu

uv run alembic upgrade head
exec uv run uvicorn --host 0.0.0.0 --port 5000 ctfeed:app

#!/usr/bin/env bash
set -euo pipefail
project_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd -- "$project_root"
uv sync --locked
uv run --locked python -m pdf_to_markdown.install
uv tool install --editable "$project_root" --force

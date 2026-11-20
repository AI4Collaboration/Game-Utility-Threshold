#!/usr/bin/env bash
# macOS / Linux / WSL. Never source .env, print a key, or update an existing runtime.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
command="${1:-run}"
case "$command" in run|smoke|status|report) ;; *) echo 'Usage: bash scripts/run_manager_study.sh [run|smoke|status|report]' >&2; exit 2;; esac
if [[ ! -f .venv-manager/.ready ]]; then
  if [[ -f runs/manager-study-v1/plan.json ]]; then
    echo 'The live study already exists but its frozen runtime is missing. Do not reinstall or start over; contact the researcher.' >&2
    exit 2
  fi
  python3 -c 'import sys; assert sys.version_info >= (3,11), "Python 3.11+ is required"'
  python3 -m venv .venv-manager
  .venv-manager/bin/python -m pip install '.[inspect,figures]'
  .venv-manager/bin/python -m pip check
  touch .venv-manager/.ready
fi
exec .venv-manager/bin/python manager_study.py "$command"

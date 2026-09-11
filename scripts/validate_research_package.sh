#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
analysis_copy="$(mktemp)"
trap 'rm -f "$analysis_copy"' EXIT

cd "$project_root"
python3 -m unittest discover -s tests
python3 analyze_phase_one_results.py \
  results/phase_one_model_eval.json \
  --policies results/phase_one_policy_baselines.json \
  --output "$analysis_copy"
cmp results/phase_one_analysis.json "$analysis_copy"
python3 scripts/verify_artifact_manifest.py results/phase_one_checksums.sha256
python3 scripts/verify_artifact_manifest.py results/coordination_games_checksums.sha256

cd "$project_root/lean"
lake build
lake exe parity_check >/dev/null

cd "$project_root"
python3 -m unittest tests.test_lean_parity

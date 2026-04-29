#!/usr/bin/env bash
set -euo pipefail

# Rebuild every generated artifact the static web app reads after market data
# changes. Keep the simulation end-date tied to the newest warehouse bar so
# scheduled refreshes do not silently leave the UI on an old date.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PRICE_END="$(uv run python - <<'PY'
from pathlib import Path
import pandas as pd

path = Path('data/warehouse/daily_prices.csv')
if not path.exists():
    raise SystemExit('data/warehouse/daily_prices.csv does not exist; run build-warehouse first')
prices = pd.read_csv(path, usecols=['date'])
if prices.empty:
    raise SystemExit('data/warehouse/daily_prices.csv is empty')
print(prices['date'].astype(str).max())
PY
)"

uv run python -m snusmic_pipeline run-sim --start "${SIM_START:-2021-01-04}" --end "$PRICE_END"
uv run python -m snusmic_pipeline export-web --warehouse data/warehouse --sim data/sim --out data/web

# Strategy-search artifacts are optional in local clones, but when the Optuna
# export exists the product pages should use the same source-of-truth data/web
# artifact as the rest of the dashboard.
if [ -f data/optuna/exports/trials.csv ]; then
  uv run python scripts/export_optuna_artifacts.py --trials-csv data/optuna/exports/trials.csv --out data/web
fi

mkdir -p apps/web/public/downloads apps/web/public/artifacts
cp data/web/table-download-reports.csv apps/web/public/downloads/snusmic-reports.csv
cp data/web/table-download-strategies.csv apps/web/public/downloads/snusmic-strategies.csv
cp data/web/data-quality-download.csv apps/web/public/downloads/snusmic-data-quality.csv

for artifact in strategy-runs.json optuna-trials.json parameter-importance.json; do
  if [ -f "data/web/$artifact" ]; then
    cp "data/web/$artifact" "apps/web/public/artifacts/$artifact"
  fi
done

printf 'Refreshed web artifacts through %s\n' "$PRICE_END"

# SNUSMIC Google Finance Sheets

This project collects the first seven pages of SNUSMIC equity research reports, downloads the linked PDFs, extracts ticker and target-price data, computes post-publication return analytics, and publishes a GitHub Pages dashboard. Google Sheets sync remains available as an optional output.

## Local Run

```bash
uv sync --group dev
uv run python -m snusmic_pipeline sync --pages 1-7 --skip-sheet
uv run python -m snusmic_pipeline build-warehouse
uv run python -m snusmic_pipeline refresh-prices
uv run python -m snusmic_pipeline run-backtest
uv run python -m snusmic_pipeline build-site
python scripts/prepare_quarto_site.py
quarto render site/quarto
```

The local run writes:

- `data/pdfs/` for downloaded PDFs
- `data/manifest.json` for source metadata and file hashes
- `data/extracted_reports.csv` for extracted rows
- `data/price_metrics.json` for yfinance post-publication metrics
- `data/portfolio_backtests.json` for cohort backtests
- `data/warehouse/` for Quant Engine v3 normalized CSV tables
- `data/quant_v3/` for Quarto-ready walk-forward strategy artifacts
- `site/public/` for the generated dashboard artifact

## Quant Engine v3

The v3 engine is event-driven rather than cohort-based. Reports accumulate into a candidate pool after publication, strategies select an execution pool from those candidates, and realized/live log returns are tracked separately.

Key commands:

```bash
uv run python -m snusmic_pipeline build-warehouse
uv run python -m snusmic_pipeline refresh-prices
uv run python -m snusmic_pipeline run-backtest
uv run python -m snusmic_pipeline optimize-strategies --trials 25
uv run python -m snusmic_pipeline export-dashboard
```

The default strategy set compares MTT/RS/target filters with `1/N`, Sharpe, Sortino, CVaR, Calmar, max-return, and min-variance weighting. Optuna maximizes cumulative log wealth. RS is computed inside the SNUSMIC candidate universe only, and future reports are excluded from earlier RS ranks.

## Google Sheets Sync

Create a Google Cloud service account, share the target Google Sheet with the service account email as an editor, then set:

```bash
export GOOGLE_SERVICE_ACCOUNT_JSON='{"type":"service_account",...}'
export GOOGLE_SHEET_ID='your-spreadsheet-id'
uv run python -m snusmic_pipeline sync --pages 1-5 --sheet-id "$GOOGLE_SHEET_ID"
```

OpenDataLoader PDF is used as a fallback extraction layer when the fast `pypdf` pass cannot extract enough text or cannot find ticker/target-price data. The package requires Java 11+. Hybrid OCR can be enabled after starting the backend:

```bash
uv run opendataloader-pdf-hybrid --port 5002 --force-ocr --ocr-lang "ko,en"
uv run python -m snusmic_pipeline sync --pages 1-7 --opendataloader-hybrid docling-fast
```

The GitHub workflow installs Java and can run the same command path. Keep hybrid OCR off unless scanned PDFs appear, because the OCR stack is much heavier than the fast local parser.

## GitHub Pages

The workflow checks only `http://snusmic.com/research/` on scheduled runs. If page one has no new report links compared with `data/manifest.json`, it skips the heavy sync, OCR, yfinance, and Pages deployment. Manual runs can force a full refresh.

## GitHub Actions

The workflow runs daily at 23:30 UTC, which is 08:30 KST, and can also be run manually. Configure repository secrets:

- `GOOGLE_SERVICE_ACCOUNT_JSON`
- `GOOGLE_SHEET_ID`

The workflow commits changed PDFs, manifest data, and CSV output back to the default branch.

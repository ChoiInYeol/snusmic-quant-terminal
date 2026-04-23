# SNUSMIC Google Finance Sheets

This project collects the first five pages of SNUSMIC equity research reports, downloads the linked PDFs, extracts ticker and target-price data, and syncs the result to Google Sheets with `GOOGLEFINANCE` formulas.

## Local Run

```bash
uv sync --group dev
uv run python -m snusmic_pipeline sync --pages 1-5 --skip-sheet
```

The local run writes:

- `data/pdfs/` for downloaded PDFs
- `data/manifest.json` for source metadata and file hashes
- `data/extracted_reports.csv` for extracted rows

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
uv run python -m snusmic_pipeline sync --pages 1-5 --opendataloader-hybrid docling-fast
```

The GitHub workflow installs Java and can run the same command path. Keep hybrid OCR off unless scanned PDFs appear, because the OCR stack is much heavier than the fast local parser.

## GitHub Actions

The workflow runs daily at 23:30 UTC, which is 08:30 KST, and can also be run manually. Configure repository secrets:

- `GOOGLE_SERVICE_ACCOUNT_JSON`
- `GOOGLE_SHEET_ID`

The workflow commits changed PDFs, manifest data, and CSV output back to the default branch.

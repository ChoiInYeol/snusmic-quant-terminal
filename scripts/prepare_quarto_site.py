from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DATA = ROOT / "data"
QUARTO_DATA = ROOT / "site" / "quarto" / "data"


def main() -> int:
    QUARTO_DATA.mkdir(parents=True, exist_ok=True)
    for name in ["reports.json", "price_metrics.json", "portfolio_backtests.json"]:
        source = SOURCE_DATA / name
        if name == "reports.json":
            source = ROOT / "site" / "public" / "data" / "reports.json"
        if not source.exists():
            raise FileNotFoundError(f"Missing source for Quarto data copy: {source}")
        shutil.copy2(source, QUARTO_DATA / name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

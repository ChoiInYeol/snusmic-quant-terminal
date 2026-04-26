from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ReportMeta(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    page: int
    ordinal: int
    date: str
    title: str
    company: str
    slug: str
    post_url: str
    pdf_url: str


class DownloadedPdf(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    meta: ReportMeta
    path: Path | None
    sha256: str | None
    status: str
    note: str = ""


class ExtractedReport(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    meta: ReportMeta
    pdf_path: Path | None
    report_current_price: float | None = None
    ticker: str = ""
    exchange: str = ""
    rating: str = ""
    bear_target: float | None = None
    base_target: float | None = None
    bull_target: float | None = None
    target_currency: str = ""
    target_price_detail: str = ""
    investment_points: str = ""
    extraction_status: str = "pending"
    note: str = ""
    raw_matches: dict[str, str] = Field(default_factory=dict)

    @property
    def pdf_filename(self) -> str:
        return self.pdf_path.name if self.pdf_path else ""


def model_rows(items: list[BaseModel]) -> list[dict[str, Any]]:
    """Serialize a list of Pydantic models to CSV/JSON-friendly row dicts."""
    return [item.model_dump(mode="json") for item in items]

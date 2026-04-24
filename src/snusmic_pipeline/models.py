from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class ReportMeta:
    page: int
    ordinal: int
    date: str
    title: str
    company: str
    slug: str
    post_url: str
    pdf_url: str


@dataclass
class DownloadedPdf:
    meta: ReportMeta
    path: Path | None
    sha256: str | None
    status: str
    note: str = ""


@dataclass
class ExtractedReport:
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
    raw_matches: dict[str, str] = field(default_factory=dict)

    @property
    def pdf_filename(self) -> str:
        return self.pdf_path.name if self.pdf_path else ""

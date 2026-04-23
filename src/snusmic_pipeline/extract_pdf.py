from __future__ import annotations

import re
from pathlib import Path

from pypdf import PdfReader

from .models import DownloadedPdf, ExtractedReport

_TICKER_RE = re.compile(r"\(([A-Z0-9]{1,10})\)")
_TITLE_TICKER_RE = re.compile(r"([A-Z]{1,6})\s*(?:US\s*)?(?:Equity|NASDAQ|NYSE|TSE|TYO)", re.IGNORECASE)
_CURRENT_PRICE_RE = re.compile(r"현재\s*주가\s*[:：]?\s*([$₩]?\s*[0-9][0-9,]*(?:\.[0-9]+)?)", re.IGNORECASE)
_TARGET_PRICE_RE = re.compile(r"목표\s*주가\s*[:：]?\s*([$₩¥]?\s*[0-9][0-9,]*(?:\.[0-9]+)?)", re.IGNORECASE)
_PRE_TARGET_PRICE_RE = re.compile(
    r"([$₩¥]?\s*[0-9][0-9,]*(?:\.[0-9]+)?)[ \t]*원?[을를]?[ \t]*(?:[A-Za-z]+[ \t]+case[ \t]+)?목표[ \t]*주가",
    re.IGNORECASE,
)
_EN_TARGET_PRICE_RE = re.compile(
    r"(?:target\s+price|price\s+target|fair\s+value|목표\s*주가)[^0-9$₩¥]{0,80}([$₩¥]?\s*[0-9][0-9,]*(?:\.[0-9]+)?)",
    re.IGNORECASE,
)
_SCENARIO_RE = re.compile(
    r"\b(Bear|Base|Bull)\b[^0-9$₩]{0,80}([$₩]?\s*[0-9][0-9,]*(?:\.[0-9]+)?)",
    re.IGNORECASE,
)
_INVESTMENT_SECTION_RE = re.compile(
    r"(투자포인트|Investment\s+Point|Investment\s+points|Key\s+Points|Why\s+invest|Valuation)\s*[:：]?\s*(.{80,900})",
    re.IGNORECASE | re.DOTALL,
)

KNOWN_EXCHANGES = {
    "GLNG": "NASDAQ",
    "CAMT": "NASDAQ",
    "LITE": "NASDAQ",
    "IRMD": "NASDAQ",
    "SXT": "NYSE",
    "IMAX": "NYSE",
    "ESTA": "NASDAQ",
    "CRWV": "NASDAQ",
    "GLW": "NYSE",
    "LIF": "NASDAQ",
    "DOCS": "NYSE",
    "SRAD": "NASDAQ",
    "TEM": "NASDAQ",
    "CLBT": "NASDAQ",
    "ISRG": "NASDAQ",
    "PLTR": "NASDAQ",
    "FLNC": "NASDAQ",
    "LEU": "NYSE",
    "6857": "TYO",
    "4680": "TYO",
    "5253": "TYO",
    "2124": "TYO",
    "5726": "TYO",
    "GRND": "NYSE",
    "FNKO": "NASDAQ",
    "LEVI": "NYSE",
}

KNOWN_COMPANY_TICKERS = {
    "Golar LNG": "GLNG",
    "Camtek": "CAMT",
    "Lumentum Holdings Inc": "LITE",
    "Iradimed Corporation": "IRMD",
    "Sensient Technologies Corp": "SXT",
    "IMAX Corp": "IMAX",
    "JAC recruitment Co. Ltd": "2124",
    "Establishment Labs Holdings": "ESTA",
    "Coreweave": "CRWV",
    "Corning": "GLW",
    "Life360 Inc": "LIF",
    "Doximity": "DOCS",
    "Sportradar": "SRAD",
    "Tempus AI Inc": "TEM",
    "Cellebrite DI": "CLBT",
    "Advantest Corporation": "6857",
    "Round One Corp": "4680",
    "Cover Corp": "5253",
    "Grindr Inc.": "GRND",
    "Funko Inc.": "FNKO",
    "Levi Strauss & Co": "LEVI",
    "Intuitive Surgical": "ISRG",
    "OSAKA Titanium Technologies Co.,Ltd.": "5726",
    "Palantir Technologies Inc.": "PLTR",
    "Fluence Energy Inc.": "FLNC",
    "Centrus Energy Corp": "LEU",
}


def parse_money(value: str | None) -> float | None:
    if not value:
        return None
    cleaned = value.replace("$", "").replace("₩", "").replace("¥", "").replace(",", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def compact_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def extract_investment_points(text: str) -> str:
    search_area = text[:12000]
    match = _INVESTMENT_SECTION_RE.search(search_area)
    if match:
        snippet = compact_text(match.group(2))
    else:
        paragraphs = [compact_text(part) for part in re.split(r"\n\s*\n", text[:5000]) if len(compact_text(part)) >= 80]
        snippet = paragraphs[1] if len(paragraphs) > 1 else (paragraphs[0] if paragraphs else "")
    if len(snippet) > 420:
        snippet = snippet[:417].rstrip() + "..."
    return snippet


def extract_text_from_pdf(path: Path, max_pages: int | None = None) -> str:
    reader = PdfReader(str(path))
    pages = reader.pages[:max_pages] if max_pages else reader.pages
    return "\n".join(page.extract_text() or "" for page in pages)


def target_price_from_text(text: str) -> tuple[float | None, str]:
    for pattern in [_PRE_TARGET_PRICE_RE, _TARGET_PRICE_RE, _EN_TARGET_PRICE_RE]:
        match = pattern.search(text)
        if match:
            value = parse_money(match.group(1))
            if value is not None:
                return value, match.group(0)
    return None, ""


def ticker_from_text(text: str, fallback_company: str = "") -> str:
    known = KNOWN_COMPANY_TICKERS.get(fallback_company)
    if known:
        return known
    title_match = _TITLE_TICKER_RE.search(text[:2000])
    if title_match:
        return title_match.group(1).upper()
    candidates = [match.group(1) for match in _TICKER_RE.finditer(text)]
    for candidate in candidates:
        if candidate.isdigit() and len(candidate) == 6:
            return candidate
    for candidate in candidates:
        if re.fullmatch(r"[A-Z]{1,6}", candidate):
            return candidate
    return ""


def infer_exchange_and_symbol(ticker: str) -> tuple[str, str, str]:
    if not ticker:
        return "", "", "Ticker not found"
    if ticker.isdigit() and len(ticker) == 6:
        return "KRX", f"KRX:{ticker}", "Korean numeric ticker; exchange prefix inferred as KRX"
    exchange = KNOWN_EXCHANGES.get(ticker.upper(), "")
    if exchange:
        return exchange, f"{exchange}:{ticker.upper()}", ""
    return "", ticker.upper(), "Exchange not mapped; verify GoogleFinance symbol"


def infer_currency(text: str, ticker: str) -> str:
    if ticker.isdigit() and len(ticker) == 6:
        return "KRW"
    first_page = text[:3000]
    if "$" in first_page or "USD" in first_page.upper():
        return "USD"
    if ticker in {"6857", "4680", "5253", "2124", "5726"}:
        return "JPY"
    return "USD"


def parse_report_text(text: str, fallback_company: str = "") -> dict[str, object]:
    ticker = ticker_from_text(text, fallback_company=fallback_company)
    current_match = _CURRENT_PRICE_RE.search(text)
    single_target, target_raw = target_price_from_text(text)

    scenario_values: dict[str, float] = {}
    for match in _SCENARIO_RE.finditer(text[:15000]):
        scenario = match.group(1).lower()
        if scenario not in scenario_values:
            value = parse_money(match.group(2))
            if value is not None:
                scenario_values[scenario] = value

    base_target = scenario_values.get("base", single_target)
    if single_target is not None and (
        "base" in target_raw.lower()
        or base_target is None
        or (single_target > 1000 and base_target < single_target * 0.2)
    ):
        base_target = single_target
    exchange, googlefinance_symbol, exchange_note = infer_exchange_and_symbol(ticker)
    notes = []
    if exchange_note:
        notes.append(exchange_note)
    if base_target is None:
        notes.append("Target price not found")
    if not ticker:
        notes.append("Ticker not found")

    return {
        "ticker": ticker,
        "exchange": exchange,
        "googlefinance_symbol": googlefinance_symbol,
        "report_current_price": parse_money(current_match.group(1)) if current_match else None,
        "bear_target": scenario_values.get("bear"),
        "base_target": base_target,
        "bull_target": scenario_values.get("bull"),
        "target_currency": infer_currency(text, ticker),
        "investment_points": extract_investment_points(text),
        "status": "ok" if ticker and base_target is not None else "needs_review",
        "note": "; ".join(notes),
        "raw_matches": {
            "company": fallback_company,
            "current_price": current_match.group(0) if current_match else "",
            "target_price": target_raw,
        },
    }


def extract_report(download: DownloadedPdf, max_pages: int = 4) -> ExtractedReport:
    report = ExtractedReport(meta=download.meta, pdf_path=download.path)
    if not download.path:
        report.extraction_status = download.status
        report.note = download.note
        return report
    try:
        text = extract_text_from_pdf(download.path, max_pages=max_pages)
    except Exception as exc:  # noqa: BLE001 - keep one bad PDF from stopping the batch
        report.extraction_status = "text_extract_failed"
        report.note = str(exc)
        return report

    parsed = parse_report_text(text, fallback_company=download.meta.company)
    report.ticker = str(parsed["ticker"])
    report.exchange = str(parsed["exchange"])
    report.googlefinance_symbol = str(parsed["googlefinance_symbol"])
    report.report_current_price = parsed["report_current_price"]  # type: ignore[assignment]
    report.bear_target = parsed["bear_target"]  # type: ignore[assignment]
    report.base_target = parsed["base_target"]  # type: ignore[assignment]
    report.bull_target = parsed["bull_target"]  # type: ignore[assignment]
    report.target_currency = str(parsed["target_currency"])
    report.investment_points = str(parsed["investment_points"])
    report.extraction_status = str(parsed["status"])
    report.note = str(parsed["note"])
    report.raw_matches = parsed["raw_matches"]  # type: ignore[assignment]
    return report

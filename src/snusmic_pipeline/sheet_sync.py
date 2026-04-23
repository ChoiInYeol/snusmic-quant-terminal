from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .models import ExtractedReport

REPORT_SHEET = "리포트_1-5페이지"
SUMMARY_SHEET = "요약"
LOG_SHEET = "검증_로그"

REPORT_HEADERS = [
    "페이지",
    "순번",
    "게시일",
    "리포트명",
    "종목명",
    "티커",
    "거래소",
    "GoogleFinance 심볼",
    "PDF URL",
    "PDF 파일명",
    "리포트 현재주가",
    "Bear 목표가",
    "Base 목표가",
    "Bull 목표가",
    "목표가 통화",
    "투자포인트",
    "GoogleFinance 현재가",
    "Base 대비 괴리율",
    "추출 상태",
    "비고",
]


@dataclass(frozen=True)
class SheetPayload:
    report_values: list[list[Any]]
    summary_values: list[list[Any]]
    log_values: list[list[Any]]


def _number_or_blank(value: float | None) -> float | str:
    return "" if value is None else value


def build_report_rows(reports: list[ExtractedReport]) -> list[list[Any]]:
    rows: list[list[Any]] = [REPORT_HEADERS]
    for index, report in enumerate(reports, start=2):
        current_formula = f'=IFERROR(GOOGLEFINANCE($H{index},"price"),"")'
        upside_formula = f'=IF(OR($M{index}="",$Q{index}=""),"",$M{index}/$Q{index}-1)'
        rows.append(
            [
                report.meta.page,
                report.meta.ordinal,
                report.meta.date,
                report.meta.title,
                report.meta.company,
                report.ticker,
                report.exchange,
                report.googlefinance_symbol,
                report.meta.pdf_url,
                report.pdf_filename,
                _number_or_blank(report.report_current_price),
                _number_or_blank(report.bear_target),
                _number_or_blank(report.base_target),
                _number_or_blank(report.bull_target),
                report.target_currency,
                report.investment_points,
                current_formula if report.googlefinance_symbol else "",
                upside_formula if report.base_target is not None and report.googlefinance_symbol else "",
                report.extraction_status,
                report.note,
            ]
        )
    return rows


def build_summary_rows() -> list[list[Any]]:
    return [
        ["Metric", "Value"],
        ["Total reports", f'=COUNTA(\'{REPORT_SHEET}\'!D2:D)'],
        ["Extracted OK", f'=COUNTIF(\'{REPORT_SHEET}\'!S2:S,"ok")'],
        ["Needs review", f'=COUNTIF(\'{REPORT_SHEET}\'!S2:S,"<>ok")'],
        ["Top upside rows", f'=SORT(FILTER(\'{REPORT_SHEET}\'!D2:T,\'{REPORT_SHEET}\'!R2:R<>""),15,FALSE)'],
    ]


def build_log_rows(reports: list[ExtractedReport], page_counts: dict[int, int], logs: list[str]) -> list[list[Any]]:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rows: list[list[Any]] = [["UTC 실행 시각", now], [], ["페이지", "수집 건수"]]
    rows.extend([[page, count] for page, count in sorted(page_counts.items())])
    rows.extend([[], ["상태", "리포트명", "비고"]])
    for report in reports:
        if report.extraction_status != "ok" or report.note:
            rows.append([report.extraction_status, report.meta.title, report.note])
    if logs:
        rows.extend([[], ["로그"]])
        rows.extend([[message] for message in logs])
    return rows


def build_payload(reports: list[ExtractedReport], page_counts: dict[int, int], logs: list[str]) -> SheetPayload:
    return SheetPayload(
        report_values=build_report_rows(reports),
        summary_values=build_summary_rows(),
        log_values=build_log_rows(reports, page_counts, logs),
    )


def load_service_account_info() -> dict[str, Any]:
    raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
    if not raw:
        raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON is required for Sheets sync")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON is not valid JSON") from exc


def sync_google_sheet(spreadsheet_id: str, payload: SheetPayload) -> None:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    credentials = service_account.Credentials.from_service_account_info(
        load_service_account_info(),
        scopes=["https://www.googleapis.com/auth/spreadsheets"],
    )
    service = build("sheets", "v4", credentials=credentials, cache_discovery=False)
    sheets = service.spreadsheets()

    metadata = sheets.get(spreadsheetId=spreadsheet_id).execute()
    existing = {sheet["properties"]["title"]: sheet["properties"]["sheetId"] for sheet in metadata.get("sheets", [])}
    missing_titles = [title for title in [REPORT_SHEET, SUMMARY_SHEET, LOG_SHEET] if title not in existing]
    if missing_titles:
        sheets.batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": title}}} for title in missing_titles]},
        ).execute()
        metadata = sheets.get(spreadsheetId=spreadsheet_id).execute()
        existing = {sheet["properties"]["title"]: sheet["properties"]["sheetId"] for sheet in metadata.get("sheets", [])}

    updates = [
        (REPORT_SHEET, payload.report_values),
        (SUMMARY_SHEET, payload.summary_values),
        (LOG_SHEET, payload.log_values),
    ]
    for title, values in updates:
        sheets.values().clear(spreadsheetId=spreadsheet_id, range=f"'{title}'!A:Z").execute()
        sheets.values().update(
            spreadsheetId=spreadsheet_id,
            range=f"'{title}'!A1",
            valueInputOption="USER_ENTERED",
            body={"values": values},
        ).execute()

    report_sheet_id = existing[REPORT_SHEET]
    sheets.batchUpdate(
        spreadsheetId=spreadsheet_id,
        body={
            "requests": [
                {
                    "updateSheetProperties": {
                        "properties": {"sheetId": report_sheet_id, "gridProperties": {"frozenRowCount": 1}},
                        "fields": "gridProperties.frozenRowCount",
                    }
                },
                {
                    "repeatCell": {
                        "range": {"sheetId": report_sheet_id, "startRowIndex": 0, "endRowIndex": 1},
                        "cell": {"userEnteredFormat": {"textFormat": {"bold": True}}},
                        "fields": "userEnteredFormat.textFormat.bold",
                    }
                },
                {
                    "setBasicFilter": {
                        "filter": {
                            "range": {
                                "sheetId": report_sheet_id,
                                "startRowIndex": 0,
                                "endRowIndex": max(1, len(payload.report_values)),
                                "startColumnIndex": 0,
                                "endColumnIndex": len(REPORT_HEADERS),
                            }
                        }
                    }
                },
            ]
        },
    ).execute()

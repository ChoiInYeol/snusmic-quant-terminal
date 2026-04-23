from __future__ import annotations

import html
import re
from typing import Iterable

import requests

from .models import ReportMeta

BASE_URL = "http://snusmic.com"
POSTS_ENDPOINT = f"{BASE_URL}/wp-json/wp/v2/posts"
DEFAULT_TIMEOUT = 30

_PDF_RE = re.compile(r'href=["\']([^"\']+?\.pdf)["\']', re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")


def parse_pages(value: str) -> list[int]:
    pages: set[int] = set()
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start_text, end_text = part.split("-", 1)
            start = int(start_text)
            end = int(end_text)
            if start > end:
                raise ValueError(f"Invalid page range: {part}")
            pages.update(range(start, end + 1))
        else:
            pages.add(int(part))
    if not pages:
        raise ValueError("At least one page is required")
    return sorted(pages)


def clean_html_text(value: str) -> str:
    unescaped = html.unescape(value or "")
    return _TAG_RE.sub("", unescaped).strip()


def company_from_title(title: str) -> str:
    if "," in title:
        return title.split(",", 1)[1].strip()
    return title.strip()


def pdf_url_from_content(rendered_content: str) -> str:
    match = _PDF_RE.search(html.unescape(rendered_content or ""))
    return match.group(1) if match else ""


def fetch_page(page: int, session: requests.Session | None = None) -> list[dict]:
    client = session or requests.Session()
    response = client.get(
        POSTS_ENDPOINT,
        params={
            "per_page": 12,
            "page": page,
            "_fields": "date,link,title,slug,content",
        },
        headers={"User-Agent": "Mozilla/5.0 snusmic-google-finance-sheets/0.1"},
        timeout=DEFAULT_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


def fetch_reports(pages: Iterable[int], session: requests.Session | None = None) -> list[ReportMeta]:
    reports: list[ReportMeta] = []
    for page in pages:
        posts = fetch_page(page, session=session)
        for ordinal, post in enumerate(posts, start=1):
            title = clean_html_text(post.get("title", {}).get("rendered", ""))
            content = post.get("content", {}).get("rendered", "")
            reports.append(
                ReportMeta(
                    page=page,
                    ordinal=ordinal,
                    date=str(post.get("date", "")),
                    title=title,
                    company=company_from_title(title),
                    slug=str(post.get("slug", "")),
                    post_url=str(post.get("link", "")),
                    pdf_url=pdf_url_from_content(content),
                )
            )
    return reports

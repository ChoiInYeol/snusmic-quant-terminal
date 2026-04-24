from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path

RESEARCH_PAGE_URL = "http://snusmic.com/research/"
_POST_LINK_RE = re.compile(r'href=["\'](http://snusmic\.com/equity-research-[^"\']+/)["\']')


def fetch_research_page_html(url: str = RESEARCH_PAGE_URL) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 snusmic-quant-terminal/0.2"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def parse_page_one_post_urls(html: str) -> list[str]:
    seen: set[str] = set()
    urls: list[str] = []
    for match in _POST_LINK_RE.finditer(html):
        url = match.group(1)
        if url not in seen:
            seen.add(url)
            urls.append(url)
    return urls[:12]


def manifest_post_urls(path: Path) -> set[str]:
    if not path.exists():
        return set()
    data = json.loads(path.read_text(encoding="utf-8"))
    return {str(item.get("post_url", "")) for item in data if item.get("post_url")}


def new_report_urls(manifest_path: Path, html: str | None = None) -> list[str]:
    page_urls = parse_page_one_post_urls(html if html is not None else fetch_research_page_html())
    known = manifest_post_urls(manifest_path)
    return [url for url in page_urls if url not in known]

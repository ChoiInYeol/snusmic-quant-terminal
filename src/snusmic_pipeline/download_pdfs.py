from __future__ import annotations

import hashlib
import re
from pathlib import Path
from urllib.parse import unquote

import requests

from .fetch_index import DEFAULT_TIMEOUT
from .models import DownloadedPdf, ReportMeta

_SAFE_FILENAME_RE = re.compile(r"[\\/:*?\"<>|]+")
_LEGACY_SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9._%-]+")


def safe_pdf_filename(meta: ReportMeta) -> str:
    date = (meta.date or "unknown")[:10]
    slug = unquote(meta.slug or hashlib.sha256(meta.pdf_url.encode("utf-8")).hexdigest()[:16])
    safe_slug = _SAFE_FILENAME_RE.sub("-", slug).strip(".- ") or "report"
    return f"{date}_{safe_slug}.pdf"


def legacy_pdf_filename(meta: ReportMeta) -> str:
    date = (meta.date or "unknown")[:10]
    slug = meta.slug or hashlib.sha256(meta.pdf_url.encode("utf-8")).hexdigest()[:16]
    safe_slug = _LEGACY_SAFE_FILENAME_RE.sub("-", slug).strip(".-") or "report"
    return f"{date}_{safe_slug}.pdf"


def migrate_legacy_pdf_name(meta: ReportMeta, pdf_dir: Path) -> Path | None:
    target = pdf_dir / safe_pdf_filename(meta)
    legacy = pdf_dir / legacy_pdf_filename(meta)
    if target == legacy:
        return target if target.exists() else None
    if target.exists():
        if legacy.exists():
            legacy.unlink()
        return target
    if legacy.exists():
        legacy.rename(target)
        return target
    return None


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_pdf(
    meta: ReportMeta,
    pdf_dir: Path,
    session: requests.Session | None = None,
    force: bool = False,
) -> DownloadedPdf:
    pdf_dir.mkdir(parents=True, exist_ok=True)
    target = pdf_dir / safe_pdf_filename(meta)
    migrated = migrate_legacy_pdf_name(meta, pdf_dir)
    if migrated:
        target = migrated
    if not meta.pdf_url:
        return DownloadedPdf(meta=meta, path=None, sha256=None, status="missing_pdf_url", note="No PDF URL in post content")

    client = session or requests.Session()
    try:
        response = client.get(
            meta.pdf_url,
            headers={"User-Agent": "Mozilla/5.0 snusmic-quant-terminal/0.1"},
            timeout=DEFAULT_TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        if target.exists() and not force:
            return DownloadedPdf(meta=meta, path=target, sha256=sha256_file(target), status="reused_after_download_error", note=str(exc))
        return DownloadedPdf(meta=meta, path=None, sha256=None, status="download_failed", note=str(exc))

    content_type = response.headers.get("content-type", "")
    if "pdf" not in content_type.lower() and not response.content.startswith(b"%PDF"):
        return DownloadedPdf(meta=meta, path=None, sha256=None, status="not_pdf", note=f"Content-Type: {content_type}")

    new_hash = sha256_bytes(response.content)
    if target.exists() and not force and sha256_file(target) == new_hash:
        return DownloadedPdf(meta=meta, path=target, sha256=new_hash, status="reused", note="")

    temp = target.with_suffix(".pdf.tmp")
    temp.write_bytes(response.content)
    temp.replace(target)
    return DownloadedPdf(meta=meta, path=target, sha256=new_hash, status="downloaded", note="")


def download_all(
    reports: list[ReportMeta],
    pdf_dir: Path,
    session: requests.Session | None = None,
    force: bool = False,
) -> list[DownloadedPdf]:
    return [download_pdf(report, pdf_dir, session=session, force=force) for report in reports]

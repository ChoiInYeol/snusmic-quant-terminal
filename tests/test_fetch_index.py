from snusmic_pipeline.cli import build_parser
from snusmic_pipeline.fetch_index import clean_html_text, fetch_reports, parse_pages


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return FakeResponse(self.payload)


def test_parse_pages_range_and_list():
    assert parse_pages("1-3,5") == [1, 2, 3, 5]


def test_sync_default_pages_is_one_to_seven():
    parser = build_parser()
    args = parser.parse_args(["sync", "--no-market-data"])

    assert args.pages == "1-7"


def test_clean_html_text_unescapes_entities():
    assert clean_html_text("Equity Research, Levi Strauss &#038; Co") == "Equity Research, Levi Strauss & Co"


def test_fetch_reports_extracts_pdf_url_and_company():
    payload = [
        {
            "date": "2026-04-16T02:37:54",
            "slug": "equity-research-demo",
            "link": "http://snusmic.com/equity-research-demo/",
            "title": {"rendered": "Equity Research, Demo Corp"},
            "content": {"rendered": '<a href="http://snusmic.com/file.pdf">download</a>'},
        }
    ]
    session = FakeSession(payload)

    reports = fetch_reports([1], session=session)

    assert len(reports) == 1
    assert reports[0].company == "Demo Corp"
    assert reports[0].pdf_url == "http://snusmic.com/file.pdf"
    assert reports[0].page == 1
    assert reports[0].ordinal == 1

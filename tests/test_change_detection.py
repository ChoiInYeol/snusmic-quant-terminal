import json

from snusmic_pipeline.change_detection import new_report_urls, parse_page_one_post_urls

HTML = """
<a href="http://snusmic.com/equity-research-new/">Read More</a>
<a href="http://snusmic.com/equity-research-old/">Read More</a>
<a href="http://snusmic.com/equity-research-new/">Read More</a>
"""


def test_parse_page_one_post_urls_dedupes():
    assert parse_page_one_post_urls(HTML) == [
        "http://snusmic.com/equity-research-new/",
        "http://snusmic.com/equity-research-old/",
    ]


def test_new_report_detector_compares_manifest(tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps([{"post_url": "http://snusmic.com/equity-research-old/"}]), encoding="utf-8"
    )

    assert new_report_urls(manifest, HTML) == ["http://snusmic.com/equity-research-new/"]

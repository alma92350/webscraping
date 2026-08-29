from pathlib import Path

from app.extractor import extract_content

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_extracts_title_and_real_content_from_a_cluttered_page():
    title, text = extract_content(load("clutter_article.html"))

    assert title == "My Great Article Title"
    assert "real first paragraph" in text
    assert "second paragraph" in text
    assert "conclusion that ties the whole piece together" in text


def test_strips_nav_ads_social_and_footer_boilerplate():
    _title, text = extract_content(load("clutter_article.html"))

    assert "Home" not in text
    assert "About" not in text
    assert "Buy our stuff now" not in text
    assert "Subscribe to our newsletter" not in text
    assert "Share on Twitter" not in text
    assert "Copyright 2026" not in text


def test_minimal_real_world_page():
    title, text = extract_content(load("example_com.html"))

    assert title == "Example Domain"
    assert "This domain is for use in documentation examples" in text


def test_page_with_no_title_tag_still_extracts_a_reasonable_title_and_body():
    title, text = extract_content(load("httpbin_html.html"))

    assert title  # trafilatura pulls it from the body when there's no <title>
    assert "Availing himself of the mild" in text


def test_falls_back_gracefully_on_a_page_with_no_extractable_content():
    title, text = extract_content("<html><head></head><body></body></html>")

    assert title == "No title found"
    assert text == ""


def test_falls_back_to_title_tag_when_body_has_no_extractable_article():
    html = "<html><head><title> Just A Title </title></head><body></body></html>"
    title, _text = extract_content(html)

    assert title == "Just A Title"


def test_minimal_content_without_any_title_signal():
    html = "<html><body><p>Hi there, this is some minimal content without a title or heading.</p></body></html>"
    title, text = extract_content(html)

    assert title == "No title found"
    assert "Hi there, this is some minimal content" in text

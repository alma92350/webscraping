import pytest

from app.errors import ScrapeError
from app.security import assert_url_is_safe


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "http://127.0.0.1:8000/admin",
        "http://localhost/",
        "http://169.254.169.254/latest/meta-data/",  # cloud metadata endpoint
        "http://10.0.0.5/",
        "http://172.16.0.1/",
        "http://192.168.1.1/",
        "http://0.0.0.0/",
        "http://[::1]/",  # IPv6 loopback
    ],
)
def test_blocks_private_and_loopback_targets(url):
    with pytest.raises(ScrapeError) as exc_info:
        assert_url_is_safe(url)
    assert exc_info.value.status_code == 400


@pytest.mark.parametrize("url", ["ftp://example.com/", "file:///etc/passwd", "javascript:alert(1)"])
def test_blocks_disallowed_schemes(url):
    with pytest.raises(ScrapeError) as exc_info:
        assert_url_is_safe(url)
    assert exc_info.value.status_code == 400


def test_blocks_explicit_blocklisted_hostname():
    with pytest.raises(ScrapeError):
        assert_url_is_safe("http://metadata.google.internal/")


def test_blocks_hostname_that_fails_to_resolve():
    def fake_resolver(hostname, port):
        raise OSError("name resolution failed")

    with pytest.raises(ScrapeError) as exc_info:
        assert_url_is_safe("http://this-does-not-resolve.invalid/", resolver=fake_resolver)
    assert exc_info.value.status_code == 400


def test_blocks_hostname_that_resolves_to_a_private_address_via_injected_resolver():
    # Simulates DNS rebinding / an attacker-controlled domain that resolves
    # to an internal address, without depending on real DNS in the test.
    def fake_resolver(hostname, port):
        return [(2, 1, 6, "", ("10.1.2.3", 0))]

    with pytest.raises(ScrapeError) as exc_info:
        assert_url_is_safe("http://evil.example.com/", resolver=fake_resolver)
    assert exc_info.value.status_code == 400


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/",
        "http://example.com/some/path?x=1",
        "https://example.com:8443/path",
    ],
)
def test_allows_public_targets(url):
    def fake_resolver(hostname, port):
        return [(2, 1, 6, "", ("93.184.216.34", 0))]

    assert_url_is_safe(url, resolver=fake_resolver)


def test_missing_hostname_is_rejected():
    with pytest.raises(ScrapeError) as exc_info:
        assert_url_is_safe("http:///no-host")
    assert exc_info.value.status_code == 400

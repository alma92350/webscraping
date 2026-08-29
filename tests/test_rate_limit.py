import pytest

from app.errors import ScrapeError
from app.rate_limit import RateLimiter, assert_api_key


class FakeClock:
    def __init__(self, start: float = 0.0):
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def test_allows_requests_under_the_limit():
    clock = FakeClock()
    limiter = RateLimiter(max_requests=3, window_seconds=60, clock=clock)

    assert limiter.allow("1.2.3.4") is True
    assert limiter.allow("1.2.3.4") is True
    assert limiter.allow("1.2.3.4") is True


def test_blocks_once_limit_is_exceeded_within_window():
    clock = FakeClock()
    limiter = RateLimiter(max_requests=2, window_seconds=60, clock=clock)

    assert limiter.allow("1.2.3.4") is True
    assert limiter.allow("1.2.3.4") is True
    assert limiter.allow("1.2.3.4") is False


def test_window_resets_after_it_elapses():
    clock = FakeClock()
    limiter = RateLimiter(max_requests=1, window_seconds=10, clock=clock)

    assert limiter.allow("1.2.3.4") is True
    assert limiter.allow("1.2.3.4") is False

    clock.advance(10.1)
    assert limiter.allow("1.2.3.4") is True


def test_sliding_window_expires_individual_hits_not_the_whole_window():
    clock = FakeClock()
    limiter = RateLimiter(max_requests=2, window_seconds=10, clock=clock)

    assert limiter.allow("1.2.3.4") is True  # t=0
    clock.advance(6)
    assert limiter.allow("1.2.3.4") is True  # t=6, still 2 hits in window
    assert limiter.allow("1.2.3.4") is False  # t=6, 3rd hit blocked

    clock.advance(4.1)  # t=10.1: the t=0 hit has fallen out of the window
    assert limiter.allow("1.2.3.4") is True


def test_each_key_is_tracked_independently():
    clock = FakeClock()
    limiter = RateLimiter(max_requests=1, window_seconds=60, clock=clock)

    assert limiter.allow("1.2.3.4") is True
    assert limiter.allow("1.2.3.4") is False
    # A different client (key) is unaffected by the first one's limit.
    assert limiter.allow("5.6.7.8") is True


def test_assert_api_key_is_noop_when_no_key_is_configured():
    assert_api_key(provided=None, expected=None)
    assert_api_key(provided="anything", expected=None)


def test_assert_api_key_accepts_matching_key():
    assert_api_key(provided="secret123", expected="secret123")


@pytest.mark.parametrize("provided", [None, "", "wrong-key"])
def test_assert_api_key_rejects_missing_or_wrong_key(provided):
    with pytest.raises(ScrapeError) as exc_info:
        assert_api_key(provided=provided, expected="secret123")
    assert exc_info.value.status_code == 401

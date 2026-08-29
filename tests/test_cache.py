from app.cache import TTLCache


class FakeClock:
    def __init__(self, start: float = 0.0):
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def test_get_missing_key_returns_none():
    cache = TTLCache(ttl_seconds=60)
    assert cache.get("https://example.com/") is None


def test_set_then_get_returns_the_value():
    cache = TTLCache(ttl_seconds=60)
    cache.set("https://example.com/", ("Example", "some text"))
    assert cache.get("https://example.com/") == ("Example", "some text")


def test_value_expires_after_ttl():
    clock = FakeClock()
    cache = TTLCache(ttl_seconds=10, clock=clock)
    cache.set("https://example.com/", "value")

    clock.advance(9.9)
    assert cache.get("https://example.com/") == "value"

    clock.advance(0.2)  # now past the 10s ttl
    assert cache.get("https://example.com/") is None


def test_ttl_of_zero_disables_caching():
    cache = TTLCache(ttl_seconds=0)
    cache.set("https://example.com/", "value")
    assert cache.get("https://example.com/") is None


def test_evicts_oldest_entry_when_max_size_exceeded():
    cache = TTLCache(ttl_seconds=60, max_size=2)
    cache.set("a", "1")
    cache.set("b", "2")
    cache.set("c", "3")  # should evict "a", the least-recently-used

    assert cache.get("a") is None
    assert cache.get("b") == "2"
    assert cache.get("c") == "3"


def test_getting_an_entry_refreshes_its_recency():
    cache = TTLCache(ttl_seconds=60, max_size=2)
    cache.set("a", "1")
    cache.set("b", "2")
    cache.get("a")  # touch "a" so it's no longer the least-recently-used
    cache.set("c", "3")  # should evict "b" instead of "a"

    assert cache.get("a") == "1"
    assert cache.get("b") is None
    assert cache.get("c") == "3"

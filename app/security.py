import ipaddress
import socket
from urllib.parse import urlparse

from app.errors import ScrapeError

# Hostnames worth blocking explicitly because they don't resolve to a
# "private" IP range but still expose sensitive data (cloud metadata APIs).
BLOCKED_HOSTNAMES = {"metadata.google.internal"}


def assert_url_is_safe(url: str, *, resolver=socket.getaddrinfo) -> None:
    """Best-effort SSRF guard.

    Rejects non-http(s) schemes and hostnames that resolve to
    private/loopback/link-local/reserved addresses. This narrows the attack
    surface but is not a complete defense against DNS rebinding, since the
    browser performs its own DNS resolution when it actually fetches the
    page (after this check has passed).

    `resolver` matches the signature of socket.getaddrinfo(host, port) and
    is injectable so tests don't depend on real DNS.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ScrapeError(400, "Only http and https URLs are supported.")

    hostname = parsed.hostname
    if not hostname:
        raise ScrapeError(400, "URL is missing a hostname.")

    if hostname.lower() in BLOCKED_HOSTNAMES:
        raise ScrapeError(400, "This host is not allowed.")

    try:
        addr_infos = resolver(hostname, None)
    except OSError:
        raise ScrapeError(400, "Could not resolve host.")

    for _family, _type, _proto, _canonname, sockaddr in addr_infos:
        ip = ipaddress.ip_address(sockaddr[0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            raise ScrapeError(400, "This host resolves to a disallowed address.")

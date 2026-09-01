import ipaddress
import re
import socket

# Hostname labels per RFC 1123: letters, digits and hyphens, no scheme or path.
FQDN_PATTERN = re.compile(
    r"^(?=.{1,253}$)(?!-)[a-z0-9-]{1,63}(?<!-)(\.(?!-)[a-z0-9-]{1,63}(?<!-))*$"
)

# Cloud metadata endpoints are reachable from inside many deployments and are a
# common SSRF target, so they are blocked alongside the private ranges.
METADATA_ADDRESSES = frozenset({"169.254.169.254", "fd00:ec2::254"})


def is_private_address(address: str) -> bool:
    try:
        parsed = ipaddress.ip_address(address)
    except ValueError:
        return False
    return (
        address in METADATA_ADDRESSES
        or parsed.is_private
        or parsed.is_loopback
        or parsed.is_link_local
        or parsed.is_reserved
        or parsed.is_multicast
        or parsed.is_unspecified
    )


def resolve_addresses(fqdn: str) -> list[str]:
    """Resolve a hostname to its addresses, returning [] when resolution fails."""
    try:
        info = socket.getaddrinfo(fqdn, None)
    except socket.gaierror:
        return []
    return sorted({entry[4][0] for entry in info})


def is_allowed_target(fqdn: str, *, allow_private: bool) -> tuple[bool, str | None]:
    """Report whether Heal may probe a hostname.

    Returns (allowed, reason). Blocking happens after resolution so that a
    public-looking name pointing at a private address is still rejected.
    """
    if allow_private:
        return True, None
    if is_private_address(fqdn):
        return False, f"{fqdn} is a private or reserved address"
    for address in resolve_addresses(fqdn):
        if is_private_address(address):
            return False, f"{fqdn} resolves to private address {address}"
    return True, None

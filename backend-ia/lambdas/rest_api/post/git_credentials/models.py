import ipaddress
import re
from dataclasses import dataclass
from urllib.parse import urlsplit

# Providers that need no base_url; any other provider must send one
KNOWN_PROVIDERS = {
    "github": "https://api.github.com",
    "gitlab": "https://gitlab.com/api/v4",
}
_PROVIDER_PATTERN = re.compile(r"[a-z0-9][a-z0-9_-]{1,39}")
# Tokens go in HTTP headers later: printable ASCII only, no spaces
_TOKEN_PATTERN = re.compile(r"[\x21-\x7e]{1,4096}")


def _validate_base_url(url):
    """HTTPS URL on a public host, without credentials, query or fragment."""
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname:
        raise ValueError("base_url must be an https URL")
    if parts.username or parts.password or parts.query or parts.fragment:
        raise ValueError("base_url must not contain credentials, query or fragment")
    host = parts.hostname
    try:
        is_public = ipaddress.ip_address(host).is_global
    except ValueError:
        is_public = host != "localhost" and not host.endswith(".localhost")
    if not is_public:
        raise ValueError("base_url must be a public host")
    return url.rstrip("/")


@dataclass
class SaveCredentialsRequest:
    """Validated body of POST /git_credentials."""

    provider: str
    token: str
    username: str | None = None
    base_url: str | None = None

    def __post_init__(self):
        if not isinstance(self.provider, str) or not _PROVIDER_PATTERN.fullmatch(
            self.provider.strip().lower()
        ):
            raise ValueError(
                "provider must be 2-40 characters: lowercase letters, digits, '-' or '_'"
            )
        self.provider = self.provider.strip().lower()

        if not isinstance(self.token, str) or not _TOKEN_PATTERN.fullmatch(
            self.token.strip()
        ):
            raise ValueError(
                "token must be a non-empty string without spaces (max 4096 characters)"
            )
        self.token = self.token.strip()

        if self.username is not None and (
            not isinstance(self.username, str) or len(self.username) > 255
        ):
            raise ValueError("username must be a string of at most 255 characters")
        self.username = (self.username or "").strip() or None

        if self.base_url:
            if not isinstance(self.base_url, str):
                raise ValueError("base_url must be a string")
            self.base_url = _validate_base_url(self.base_url.strip())
        elif self.provider in KNOWN_PROVIDERS:
            self.base_url = KNOWN_PROVIDERS[self.provider]
        else:
            raise ValueError(f"base_url is required for provider '{self.provider}'")

    def __repr__(self):  # never print the token
        return f"SaveCredentialsRequest(provider={self.provider!r}, username={self.username!r}, token=***)"

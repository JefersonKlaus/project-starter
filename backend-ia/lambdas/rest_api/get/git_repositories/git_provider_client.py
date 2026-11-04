"""
Client for the Git provider APIs (GitHub, GitLab), standard library only.
Single Responsibility: Call the provider API and normalize its repositories.

The request carries the user's token and the host comes from user data (base_url),
so the HTTPS call is strict: the host must resolve only to public addresses, the
connection goes to the address that was checked (no second DNS lookup), the
certificate is verified, redirects are not followed and the answer has a size limit.
"""

import http.client
import ipaddress
import json
import socket
import ssl
from urllib.parse import urlencode, urlsplit

from models import PAGE_SIZE, Repository

TIMEOUT_SECONDS = 10
MAX_RESPONSE_BYTES = 5 * 1024 * 1024
USER_AGENT = "auto-arch-analyzer"


class GitProviderError(Exception):
    """The provider call failed; status_code is what the API answers with."""

    def __init__(self, status_code, message):
        super().__init__(message)
        self.status_code = status_code


def _github_request(page):
    query = {
        "per_page": PAGE_SIZE,
        "page": page,
        "sort": "updated",
        "affiliation": "owner,collaborator,organization_member",
    }
    return (
        "/user/repos",
        query,
        {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"},
    )


def _github_repository(item):
    return Repository(
        id=str(item["id"]),
        name=item["name"],
        full_name=item.get("full_name") or item["name"],
        description=item.get("description"),
        visibility=item.get("visibility")
        or ("private" if item.get("private") else "public"),
        default_branch=item.get("default_branch"),
        web_url=item.get("html_url"),
        clone_url=item.get("clone_url"),
        updated_at=item.get("pushed_at") or item.get("updated_at"),
    )


def _github_has_next(headers):
    return 'rel="next"' in headers.get("link", "")


def _gitlab_request(page):
    query = {
        "membership": "true",
        "order_by": "last_activity_at",
        "per_page": PAGE_SIZE,
        "page": page,
    }
    return "/projects", query, {"Accept": "application/json"}


def _gitlab_repository(item):
    return Repository(
        id=str(item["id"]),
        name=item["name"],
        full_name=item.get("path_with_namespace") or item["name"],
        description=item.get("description"),
        visibility=item.get("visibility") or "private",
        default_branch=item.get("default_branch"),
        web_url=item.get("web_url"),
        clone_url=item.get("http_url_to_repo"),
        updated_at=item.get("last_activity_at"),
    )


def _gitlab_has_next(headers):
    return bool(headers.get("x-next-page")) or 'rel="next"' in headers.get("link", "")


PROVIDERS = {
    "github": (_github_request, _github_repository, _github_has_next),
    "gitlab": (_gitlab_request, _gitlab_repository, _gitlab_has_next),
}


def list_repositories(provider, base_url, token, page):
    """One page (PAGE_SIZE) of the user's repositories. Returns (repositories, has_next_page)."""
    if provider not in PROVIDERS:
        raise GitProviderError(
            400,
            f"Listing repositories is not supported for '{provider}' (supported: github, gitlab)",
        )
    build_request, to_repository, has_next = PROVIDERS[provider]

    path, query, headers = build_request(page)
    headers = {**headers, "Authorization": f"Bearer {token}", "User-Agent": USER_AGENT}
    status, response_headers, body = https_get(
        f"{base_url.rstrip('/')}{path}?{urlencode(query)}", headers
    )

    if status in (401, 403) and not _rate_limited(status, response_headers):
        raise GitProviderError(
            409,
            f"{provider} rejected the saved credentials (expired, revoked or missing scopes)",
        )
    if status == 429 or _rate_limited(status, response_headers):
        raise GitProviderError(429, f"{provider} rate limit reached, try again later")
    if status != 200:
        raise GitProviderError(
            502, f"{provider} answered with an error (HTTP {status})"
        )

    try:
        items = json.loads(body)
        repositories = [to_repository(item) for item in items]
    except (ValueError, TypeError, KeyError):
        raise GitProviderError(
            502, f"{provider} returned an unexpected answer"
        ) from None
    return repositories, has_next(response_headers)


def _rate_limited(status, headers):
    # GitHub answers 403 for its primary (remaining 0) and secondary (retry-after) limits
    return status == 403 and (
        headers.get("x-ratelimit-remaining") == "0" or "retry-after" in headers
    )


def resolve_public_address(host, port):
    """An address of host, after checking that EVERY address it resolves to is public."""
    try:
        addresses = {
            info[4][0]
            for info in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        }
    except socket.gaierror:
        raise GitProviderError(502, f"Could not resolve {host}") from None
    if not addresses or not all(
        ipaddress.ip_address(a.split("%")[0]).is_global for a in addresses
    ):
        raise GitProviderError(
            502, "The provider address in the saved credentials is not allowed"
        )
    return sorted(addresses)[0]


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    """Connects to a pre-checked address; SNI and the certificate check use the hostname."""

    def __init__(self, host, port, address, **kwargs):
        super().__init__(host, port, **kwargs)
        self._address = address

    def connect(self):
        sock = socket.create_connection((self._address, self.port), self.timeout)
        try:
            self.sock = self._context.wrap_socket(sock, server_hostname=self.host)
        except OSError:
            sock.close()
            raise


def https_get(url, headers, ssl_context=None):
    """GET without following redirects. Returns (status, lower-case headers, body bytes)."""
    parts = urlsplit(url)
    if (
        parts.scheme != "https"
        or not parts.hostname
        or parts.username
        or parts.password
    ):
        raise GitProviderError(
            502, "The provider address in the saved credentials is not allowed"
        )
    port = parts.port or 443
    address = resolve_public_address(parts.hostname, port)

    connection = _PinnedHTTPSConnection(
        parts.hostname,
        port,
        address,
        timeout=TIMEOUT_SECONDS,
        context=ssl_context or ssl.create_default_context(),
    )
    try:
        connection.request(
            "GET",
            f"{parts.path or '/'}?{parts.query}" if parts.query else parts.path or "/",
            headers=headers,
        )
        response = connection.getresponse()
        body = response.read(MAX_RESPONSE_BYTES + 1)
    except TimeoutError:
        raise GitProviderError(504, "The provider did not answer in time") from None
    except (OSError, http.client.HTTPException):
        raise GitProviderError(502, "Could not reach the provider") from None
    finally:
        connection.close()
    if len(body) > MAX_RESPONSE_BYTES:
        raise GitProviderError(502, "The provider answer is too large")
    return response.status, {k.lower(): v for k, v in response.getheaders()}, body

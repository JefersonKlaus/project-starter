import re
from dataclasses import dataclass

PAGE_SIZE = 20  # repositories per response (fixed)
MAX_PAGE = 1000
_PROVIDER_PATTERN = re.compile(r"[a-z0-9][a-z0-9_-]{1,39}")


@dataclass
class ListRepositoriesRequest:
    """Validated query string of GET /git_repositories?provider=github&page=2"""

    provider: str
    page: int = 1

    def __post_init__(self):
        if not isinstance(self.provider, str) or not _PROVIDER_PATTERN.fullmatch(
            self.provider.strip().lower()
        ):
            raise ValueError(
                "provider is required: 2-40 characters, lowercase letters, digits, '-' or '_'"
            )
        self.provider = self.provider.strip().lower()

        try:
            self.page = int(self.page)
        except (TypeError, ValueError):
            raise ValueError("page must be an integer") from None
        if not 1 <= self.page <= MAX_PAGE:
            raise ValueError(f"page must be between 1 and {MAX_PAGE}")


@dataclass
class Repository:
    """A repository, in the same shape for every provider."""

    id: str
    name: str
    full_name: str
    description: str | None
    visibility: str  # public, private or internal
    default_branch: str | None
    web_url: str | None
    clone_url: str | None
    updated_at: str | None

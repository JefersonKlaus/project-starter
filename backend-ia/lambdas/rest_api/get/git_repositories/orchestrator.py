"""
Orchestration layer for listing git repositories.
Single Responsibility: Coordinate request parsing, credentials and the provider client.
"""

from dataclasses import asdict

from common.git_credentials import GitCredentialsRepository
from git_provider_client import list_repositories
from models import PAGE_SIZE
from request_parser import RequestParser


class GitRepositoriesOrchestrator:
    def __init__(self, repository=None):
        self.repository = repository or GitCredentialsRepository()

    def list(self, event):
        """One page of the logged user's repositories on the requested provider."""
        user_sub, request = RequestParser.parse_event(event)
        credentials = self.repository.load(user_sub, request.provider)
        repositories, has_next_page = list_repositories(
            provider=request.provider,
            base_url=credentials["base_url"],
            token=credentials["token"],
            page=request.page,
        )
        return {
            "provider": request.provider,
            "page": request.page,
            "per_page": PAGE_SIZE,
            "repositories": [asdict(repository) for repository in repositories],
            "has_next_page": has_next_page,
            "next_page": request.page + 1 if has_next_page else None,
        }

"""
Orchestration layer for saving git credentials.
Single Responsibility: Coordinate request parsing and the credentials repository.
"""

from common.git_credentials import GitCredentialsRepository
from request_parser import RequestParser


class GitCredentialsOrchestrator:
    def __init__(self, repository=None):
        self.repository = repository or GitCredentialsRepository()

    def save(self, event):
        """Save the logged user's credentials. Returns the public data (never the token)."""
        user_sub, request = RequestParser.parse_event(event)
        created = self.repository.save(
            user_sub=user_sub,
            provider=request.provider,
            base_url=request.base_url,
            token=request.token,
            username=request.username,
        )
        return {
            "provider": request.provider,
            "base_url": request.base_url,
            "username": request.username,
            "created": created,
        }

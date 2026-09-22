"""Publish the dashboard's generated files as one Git tree transaction."""
from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from typing import Any

import requests


PUBLIC_PREFIX = "frontend/public/data"


class GitHubPublishError(Exception):
    """A GitHub publishing request failed without exposing response details."""


class GitHubAuthenticationError(GitHubPublishError):
    """GitHub rejected the configured token."""


@dataclass(frozen=True)
class PublishResult:
    status: str
    commit_sha: str


@dataclass(frozen=True)
class _Head:
    commit_sha: str
    tree_sha: str


class GitHubPublisher:
    """Use GitHub's Git Data API so all dashboard files advance together."""

    BASE_URL = "https://api.github.com"
    _SUCCESS = frozenset({200, 201})

    def __init__(
        self,
        *,
        repository: str,
        branch: str,
        token: str,
        session: requests.Session | Any | None = None,
    ):
        self.repository = repository
        self.branch = branch
        self._token = token
        self.session = session or requests.Session()

    def publish(self, outputs: dict[str, bytes]) -> PublishResult:
        for attempt in range(2):
            head = self._head()
            if self._remote_hashes(head.tree_sha, outputs) == self._content_hashes(outputs):
                return PublishResult(status="unchanged", commit_sha=head.commit_sha)

            blobs = {name: self._create_blob(payload) for name, payload in outputs.items()}
            tree_sha = self._create_tree(head.tree_sha, blobs)
            commit_sha = self._create_commit(tree_sha, head.commit_sha)
            if self._update_ref(commit_sha):
                return PublishResult(status="published", commit_sha=commit_sha)
            if attempt == 1:
                break

        raise GitHubPublishError("GitHub request failed")

    def _head(self) -> _Head:
        ref = self._request("GET", f"/git/ref/heads/{self.branch}")
        commit_sha = self._required_string(ref, "object", "sha")
        commit = self._request("GET", f"/git/commits/{commit_sha}")
        tree_sha = self._required_string(commit, "tree", "sha")
        return _Head(commit_sha=commit_sha, tree_sha=tree_sha)

    def _remote_hashes(self, tree_sha: str, outputs: dict[str, bytes]) -> dict[str, str]:
        payload = self._request("GET", f"/git/trees/{tree_sha}")
        if payload.get("truncated") is True or not isinstance(payload.get("tree"), list):
            raise GitHubPublishError("GitHub response was invalid")
        prefix = f"{PUBLIC_PREFIX}/"
        wanted = set(outputs)
        return {
            item["path"][len(prefix) :]: item["sha"]
            for item in payload["tree"]
            if isinstance(item, dict)
            and item.get("type") == "blob"
            and isinstance(item.get("path"), str)
            and item["path"].startswith(prefix)
            and item["path"][len(prefix) :] in wanted
            and isinstance(item.get("sha"), str)
        }

    @staticmethod
    def _content_hashes(outputs: dict[str, bytes]) -> dict[str, str]:
        return {name: GitHubPublisher._blob_sha(payload) for name, payload in outputs.items()}

    @staticmethod
    def _blob_sha(payload: bytes) -> str:
        header = f"blob {len(payload)}\0".encode()
        return hashlib.sha1(header + payload).hexdigest()

    def _create_blob(self, payload: bytes) -> str:
        response = self._request(
            "POST",
            "/git/blobs",
            json={"content": base64.b64encode(payload).decode("ascii"), "encoding": "base64"},
        )
        return self._required_string(response, "sha")

    def _create_tree(self, base_tree: str, blobs: dict[str, str]) -> str:
        response = self._request(
            "POST",
            "/git/trees",
            json={
                "base_tree": base_tree,
                "tree": [
                    {
                        "path": f"{PUBLIC_PREFIX}/{name}",
                        "mode": "100644",
                        "type": "blob",
                        "sha": sha,
                    }
                    for name, sha in blobs.items()
                ],
            },
        )
        return self._required_string(response, "sha")

    def _create_commit(self, tree_sha: str, parent_sha: str) -> str:
        response = self._request(
            "POST",
            "/git/commits",
            json={
                "message": "data: publish OpenAQ dataset",
                "tree": tree_sha,
                "parents": [parent_sha],
            },
        )
        return self._required_string(response, "sha")

    def _update_ref(self, commit_sha: str) -> bool:
        response = self._raw_request(
            "PATCH",
            f"/git/refs/heads/{self.branch}",
            json={"sha": commit_sha, "force": False},
        )
        if response.status_code == 422:
            return False
        self._payload_or_raise(response)
        return True

    def _request(self, method: str, path: str, *, json: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._payload_or_raise(self._raw_request(method, path, json=json))

    def _raw_request(self, method: str, path: str, *, json: dict[str, Any] | None = None):
        kwargs: dict[str, Any] = {
            "headers": {
                "Authorization": f"Bearer {self._token}",
                "Accept": "application/vnd.github+json",
            },
            "timeout": (5, 30),
        }
        if json is not None:
            kwargs["json"] = json
        try:
            return self.session.request(method, f"{self.BASE_URL}/repos/{self.repository}{path}", **kwargs)
        except requests.RequestException:
            raise GitHubPublishError("GitHub request failed") from None

    def _payload_or_raise(self, response: Any) -> dict[str, Any]:
        if response.status_code in {401, 403}:
            raise GitHubAuthenticationError("GitHub authentication failed")
        if response.status_code not in self._SUCCESS:
            raise GitHubPublishError("GitHub request failed")
        try:
            payload = response.json()
        except (requests.exceptions.JSONDecodeError, ValueError):
            raise GitHubPublishError("GitHub response was invalid") from None
        if not isinstance(payload, dict):
            raise GitHubPublishError("GitHub response was invalid")
        return payload

    @staticmethod
    def _required_string(payload: dict[str, Any], *path: str) -> str:
        value: Any = payload
        for key in path:
            if not isinstance(value, dict):
                raise GitHubPublishError("GitHub response was invalid")
            value = value.get(key)
        if not isinstance(value, str) or not value:
            raise GitHubPublishError("GitHub response was invalid")
        return value

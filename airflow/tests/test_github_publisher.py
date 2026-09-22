from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from typing import Any

import pytest

from pipeline.github_publisher import GitHubAuthenticationError, GitHubPublishError, GitHubPublisher


OUTPUTS = {
    "manifest.json": b'{"datasetVersion":"test"}\n',
    "global-stations.json": b'{"features":[]}\n',
    "indonesia-latest.json": b'{"features":[]}\n',
    "indonesia-history-30d.json": b'{"stations":[]}\n',
    "indonesia-comparison.json": b'{"ranking":[]}\n',
}
PUBLIC_PREFIX = "frontend/public/data"


def git_blob_sha(payload: bytes) -> str:
    return hashlib.sha1(f"blob {len(payload)}\0".encode() + payload).hexdigest()


@dataclass
class FakeResponse:
    status_code: int
    payload: dict[str, Any]

    def json(self) -> dict[str, Any]:
        return self.payload


class FakeGitHubSession:
    """In-memory Git Data API fake; it never makes network requests."""

    def __init__(self):
        self.requests: list[tuple[str, str, dict[str, Any]]] = []
        self.ref_reads = 0
        self.created_blobs: list[dict[str, Any]] = []
        self.created_trees: list[dict[str, Any]] = []
        self.created_commits: list[dict[str, Any]] = []
        self.ref_updates: list[dict[str, Any]] = []
        self.events: list[str] = []
        self._ref_conflicts = 0
        self._authentication_failure = False
        self._truncate_recursive_tree = False
        self._counter = 0
        self.trees: dict[str, dict[str, str]] = {"tree-initial": {}}
        self.commits: dict[str, str] = {"commit-initial": "tree-initial"}
        self.head_commit = "commit-initial"

    def seed_matching_tree(self, outputs: dict[str, bytes]) -> None:
        tree = {
            f"{PUBLIC_PREFIX}/{name}": git_blob_sha(payload)
            for name, payload in outputs.items()
        }
        self.trees["tree-matching"] = tree
        self.commits["commit-matching"] = "tree-matching"
        self.head_commit = "commit-matching"

    def seed_stale_public_file_and_unrelated_file(self) -> None:
        self.trees["tree-initial"] = {
            f"{PUBLIC_PREFIX}/retired.json": "blob-retired",
            "README.md": "blob-readme",
        }

    def truncate_recursive_tree(self) -> None:
        self._truncate_recursive_tree = True

    def fail_first_ref_update_with_422(self) -> None:
        self._ref_conflicts = 1

    def fail_ref_updates_with_422(self, times: int) -> None:
        self._ref_conflicts = times

    def fail_with_401(self) -> None:
        self._authentication_failure = True

    def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
        self.requests.append((method, url, kwargs))
        if self._authentication_failure:
            return FakeResponse(401, {"message": "credential TEST_ONLY_TOKEN was rejected"})

        path = url.removeprefix("https://api.github.com/repos/acme/air-quality")
        if method == "GET" and path == "/git/ref/heads/main":
            self.ref_reads += 1
            return FakeResponse(200, {"object": {"sha": self.head_commit}})
        if method == "GET" and path.startswith("/git/commits/"):
            return FakeResponse(200, {"tree": {"sha": self.commits[self.head_commit]}})
        if method == "GET" and path.startswith("/git/trees/"):
            tree_sha, _, query = path.rpartition("/")[2].partition("?")
            if query == "recursive=1":
                entries = [
                    {"path": item_path, "type": "blob", "sha": sha}
                    for item_path, sha in self.trees[tree_sha].items()
                ]
                return FakeResponse(
                    200,
                    {"truncated": self._truncate_recursive_tree, "tree": entries},
                )
            return FakeResponse(
                200,
                {
                    "truncated": False,
                    "tree": self._non_recursive_tree(tree_sha),
                },
            )
        if method == "POST" and path == "/git/blobs":
            body = kwargs["json"]
            self.created_blobs.append(body)
            self.events.append("blob")
            return FakeResponse(
                201,
                {"sha": git_blob_sha(base64.b64decode(body["content"]))},
            )
        if method == "POST" and path == "/git/trees":
            body = kwargs["json"]
            self.created_trees.append(body)
            self.events.append("tree")
            self._counter += 1
            tree_sha = f"tree-created-{self._counter}"
            merged = dict(self.trees[body["base_tree"]])
            for entry in body["tree"]:
                if entry["sha"] is None:
                    merged.pop(entry["path"], None)
                else:
                    merged[entry["path"]] = entry["sha"]
            self.trees[tree_sha] = merged
            return FakeResponse(201, {"sha": tree_sha})
        if method == "POST" and path == "/git/commits":
            body = kwargs["json"]
            self.created_commits.append(body)
            self.events.append("commit")
            self._counter += 1
            commit_sha = f"commit-created-{self._counter}"
            self.commits[commit_sha] = body["tree"]
            return FakeResponse(201, {"sha": commit_sha})
        if method == "PATCH" and path == "/git/refs/heads/main":
            body = kwargs["json"]
            self.ref_updates.append(body)
            self.events.append("ref")
            if self._ref_conflicts:
                self._ref_conflicts -= 1
                self._advance_external_head()
                return FakeResponse(422, {"message": "reference changed; token TEST_ONLY_TOKEN"})
            self.head_commit = body["sha"]
            return FakeResponse(200, {"object": {"sha": self.head_commit}})
        raise AssertionError(f"unexpected GitHub request: {method} {path}")

    def _non_recursive_tree(self, tree_sha: str) -> list[dict[str, str]]:
        entries: dict[str, dict[str, str]] = {}
        for item_path, sha in self.trees[tree_sha].items():
            name, separator, _ = item_path.partition("/")
            entries[name] = (
                {"path": name, "type": "tree", "sha": f"tree-{name}"}
                if separator
                else {"path": name, "type": "blob", "sha": sha}
            )
        return list(entries.values())

    def _advance_external_head(self) -> None:
        self._counter += 1
        base_tree = dict(self.trees[self.commits[self.head_commit]])
        base_tree["README.md"] = f"external-{self._counter}"
        tree_sha = f"tree-external-{self._counter}"
        commit_sha = f"commit-external-{self._counter}"
        self.trees[tree_sha] = base_tree
        self.commits[commit_sha] = tree_sha
        self.head_commit = commit_sha


@pytest.fixture
def github_api() -> FakeGitHubSession:
    return FakeGitHubSession()


@pytest.fixture
def publisher(github_api: FakeGitHubSession) -> GitHubPublisher:
    return GitHubPublisher(
        repository="acme/air-quality",
        branch="main",
        token="TEST_ONLY_TOKEN",
        session=github_api,
    )


def test_unchanged_outputs_do_not_create_commit(publisher, github_api):
    github_api.seed_matching_tree(OUTPUTS)

    assert publisher.publish(OUTPUTS).status == "unchanged"
    assert github_api.created_commits == []
    assert github_api.requests[-1][1].endswith("/git/trees/tree-matching?recursive=1")


def test_truncated_recursive_tree_fails_without_creating_git_objects(publisher, github_api):
    github_api.truncate_recursive_tree()

    with pytest.raises(GitHubPublishError, match="GitHub response was invalid"):
        publisher.publish(OUTPUTS)

    assert github_api.created_blobs == []
    assert github_api.created_trees == []
    assert github_api.created_commits == []


@pytest.mark.parametrize(
    "invalid_outputs",
    [
        {**OUTPUTS, "sixth.json": b"{}\n"},
        {name: payload for name, payload in OUTPUTS.items() if name != "manifest.json"},
    ],
)
def test_publish_rejects_any_mapping_other_than_five_public_files(publisher, github_api, invalid_outputs):
    with pytest.raises(GitHubPublishError, match="output files were invalid"):
        publisher.publish(invalid_outputs)

    assert github_api.requests == []


def test_publish_deletes_stale_public_file_but_retains_unrelated_files(publisher, github_api):
    github_api.seed_stale_public_file_and_unrelated_file()

    publisher.publish(OUTPUTS)

    tree_entries = github_api.created_trees[0]["tree"]
    assert {entry["path"] for entry in tree_entries} == {
        "frontend/public/data/manifest.json",
        "frontend/public/data/global-stations.json",
        "frontend/public/data/indonesia-latest.json",
        "frontend/public/data/indonesia-history-30d.json",
        "frontend/public/data/indonesia-comparison.json",
        "frontend/public/data/retired.json",
    }
    assert {
        "path": "frontend/public/data/retired.json",
        "mode": "100644",
        "type": "blob",
        "sha": None,
    } in tree_entries
    assert github_api.trees["tree-created-1"] == {
        "README.md": "blob-readme",
        f"{PUBLIC_PREFIX}/manifest.json": git_blob_sha(OUTPUTS["manifest.json"]),
        f"{PUBLIC_PREFIX}/global-stations.json": git_blob_sha(OUTPUTS["global-stations.json"]),
        f"{PUBLIC_PREFIX}/indonesia-latest.json": git_blob_sha(OUTPUTS["indonesia-latest.json"]),
        f"{PUBLIC_PREFIX}/indonesia-history-30d.json": git_blob_sha(OUTPUTS["indonesia-history-30d.json"]),
        f"{PUBLIC_PREFIX}/indonesia-comparison.json": git_blob_sha(OUTPUTS["indonesia-comparison.json"]),
    }


def test_ref_conflict_reloads_head_and_retries_once(publisher, github_api):
    github_api.fail_first_ref_update_with_422()

    result = publisher.publish(OUTPUTS)

    assert result.status == "published"
    assert github_api.ref_reads == 2
    assert github_api.created_commits[1]["parents"] == ["commit-external-3"]


def test_publish_writes_all_files_to_one_tree_before_advancing_ref(publisher, github_api):
    result = publisher.publish(OUTPUTS)

    assert result.status == "published"
    assert result.commit_sha == "commit-created-2"
    assert github_api.events == ["blob", "blob", "blob", "blob", "blob", "tree", "commit", "ref"]
    assert github_api.created_trees == [
        {
            "base_tree": "tree-initial",
            "tree": [
                {"path": "frontend/public/data/manifest.json", "mode": "100644", "type": "blob", "sha": git_blob_sha(OUTPUTS["manifest.json"])},
                {"path": "frontend/public/data/global-stations.json", "mode": "100644", "type": "blob", "sha": git_blob_sha(OUTPUTS["global-stations.json"])},
                {"path": "frontend/public/data/indonesia-latest.json", "mode": "100644", "type": "blob", "sha": git_blob_sha(OUTPUTS["indonesia-latest.json"])},
                {"path": "frontend/public/data/indonesia-history-30d.json", "mode": "100644", "type": "blob", "sha": git_blob_sha(OUTPUTS["indonesia-history-30d.json"])},
                {"path": "frontend/public/data/indonesia-comparison.json", "mode": "100644", "type": "blob", "sha": git_blob_sha(OUTPUTS["indonesia-comparison.json"])},
            ],
        }
    ]
    assert github_api.created_commits == [
        {
            "message": "data: publish OpenAQ dataset",
            "tree": "tree-created-1",
            "parents": ["commit-initial"],
        }
    ]
    assert github_api.ref_updates == [{"sha": "commit-created-2", "force": False}]


def test_second_ref_conflict_raises_sanitized_publish_error(publisher, github_api):
    github_api.fail_ref_updates_with_422(2)

    with pytest.raises(GitHubPublishError, match="GitHub request failed") as error:
        publisher.publish(OUTPUTS)

    assert github_api.ref_reads == 2
    assert len(github_api.ref_updates) == 2
    assert "TEST_ONLY_TOKEN" not in str(error.value)


def test_authentication_error_and_requests_never_leak_token_in_url_or_body(publisher, github_api):
    github_api.fail_with_401()

    with pytest.raises(GitHubAuthenticationError, match="GitHub authentication failed") as error:
        publisher.publish(OUTPUTS)

    assert "TEST_ONLY_TOKEN" not in str(error.value)
    method, url, request = github_api.requests[0]
    assert method == "GET"
    assert request["headers"] == {"Authorization": "Bearer TEST_ONLY_TOKEN", "Accept": "application/vnd.github+json"}
    assert "TEST_ONLY_TOKEN" not in url
    assert "TEST_ONLY_TOKEN" not in repr(request.get("json"))

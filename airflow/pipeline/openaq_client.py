"""Small, resilient HTTP client for the OpenAQ API v3 endpoints we consume."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from pipeline.exceptions import AuthenticationError, OpenAQError, SchemaError


class OpenAQClient:
    BASE_URL = "https://api.openaq.org"
    DEFAULT_LIMIT = 1000
    RETRYABLE_STATUSES = (429, 500, 502, 503, 504)

    def __init__(self, api_key: str, session: requests.Session | None = None):
        self.session = session or requests.Session()
        self.session.headers.update({"X-API-Key": api_key})

        retry = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=self.RETRYABLE_STATUSES,
            allowed_methods=frozenset({"GET"}),
            respect_retry_after_header=True,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("https://", adapter)

    def url(self, path: str) -> str:
        return f"{self.BASE_URL}{path}"

    def _get(self, path: str, params: dict[str, object]) -> dict[str, Any]:
        try:
            response = self.session.get(self.url(path), params=params, timeout=(5, 30))
            if response.status_code in {401, 403}:
                raise AuthenticationError("OpenAQ authentication failed")
            response.raise_for_status()
        except requests.RequestException:
            raise OpenAQError("OpenAQ request failed") from None

        try:
            payload = response.json()
        except (requests.exceptions.JSONDecodeError, ValueError):
            raise SchemaError("OpenAQ response is not valid JSON") from None

        if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
            raise SchemaError("OpenAQ response has no results list")
        return payload

    def _paginate(
        self,
        path: str,
        params: dict[str, object],
        *,
        limit: int,
    ) -> list[dict]:
        page_number = 1
        rows: list[dict] = []
        while True:
            page_params = {**params, "limit": limit, "page": page_number}
            batch = self._get(path, page_params)["results"]
            rows.extend(batch)
            if len(batch) < limit:
                return rows
            page_number += 1

    def list_locations(
        self,
        *,
        parameters_id: int,
        iso: str | None = None,
        limit: int = DEFAULT_LIMIT,
    ) -> list[dict]:
        params: dict[str, object] = {"parameters_id": parameters_id}
        if iso:
            params["iso"] = iso
        return self._paginate("/v3/locations", params, limit=limit)

    def latest(self, location_id: int, *, limit: int = DEFAULT_LIMIT) -> list[dict]:
        return self._paginate(f"/v3/locations/{location_id}/latest", {}, limit=limit)

    def sensor_hours(
        self,
        sensor_id: int,
        start: datetime | str,
        end: datetime | str,
        *,
        limit: int = DEFAULT_LIMIT,
    ) -> list[dict]:
        params = {
            "datetime_from": self._serialize_datetime(start),
            "datetime_to": self._serialize_datetime(end),
        }
        return self._paginate(f"/v3/sensors/{sensor_id}/hours", params, limit=limit)

    @staticmethod
    def _serialize_datetime(value: datetime | str) -> str:
        return value.isoformat() if isinstance(value, datetime) else value

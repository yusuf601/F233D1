from __future__ import annotations

import copy
import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
import requests

from pipeline.exceptions import AuthenticationError, SchemaError


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "locations-page.json"
LOCATION_FIXTURE = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def page(count: int) -> dict:
    templates = LOCATION_FIXTURE["results"]
    rows = []
    for index in range(count):
        row = copy.deepcopy(templates[index % len(templates)])
        row["id"] = index + 1
        rows.append(row)
    return {
        "meta": {**LOCATION_FIXTURE["meta"], "found": count},
        "results": rows,
    }


def query(call) -> dict[str, list[str]]:
    return parse_qs(urlparse(call.request.url).query)


def test_list_locations_continues_after_full_page(client, responses):
    responses.add(responses.GET, client.url("/v3/locations"), json=page(1000), status=200)
    responses.add(responses.GET, client.url("/v3/locations"), json=page(2), status=200)
    assert len(client.list_locations(parameters_id=2, limit=1000)) == 1002
    assert [query(call)["page"] for call in responses.calls] == [["1"], ["2"]]


def test_list_locations_stops_after_short_page_and_forwards_iso(client, responses):
    responses.add(responses.GET, client.url("/v3/locations"), json=page(2), status=200)

    assert len(client.list_locations(parameters_id=2, iso="ID", limit=3)) == 2
    assert len(responses.calls) == 1
    assert query(responses.calls[0]) == {
        "parameters_id": ["2"],
        "limit": ["3"],
        "page": ["1"],
        "iso": ["ID"],
    }


def test_authentication_error_is_not_retried(client, responses):
    responses.add(responses.GET, client.url("/v3/locations"), status=401)
    with pytest.raises(AuthenticationError, match="OpenAQ authentication failed"):
        client.list_locations(parameters_id=2)
    assert len(responses.calls) == 1


@pytest.mark.parametrize("status", [429, 500, 502, 503, 504])
def test_retryable_status_is_retried(client, responses, status):
    responses.add(
        responses.GET,
        client.url("/v3/locations"),
        status=status,
        headers={"Retry-After": "0"},
    )
    responses.add(responses.GET, client.url("/v3/locations"), json=page(1), status=200)

    assert len(client.list_locations(parameters_id=2)) == 1
    assert len(responses.calls) == 2


def test_malformed_json_raises_schema_error(client, responses):
    responses.add(
        responses.GET,
        client.url("/v3/locations"),
        body="{malformed",
        status=200,
        content_type="application/json",
    )

    with pytest.raises(SchemaError, match="OpenAQ response is not valid JSON"):
        client.list_locations(parameters_id=2)


@pytest.mark.parametrize("payload", [{}, {"results": {}}, []])
def test_response_without_results_list_raises_schema_error(client, responses, payload):
    responses.add(responses.GET, client.url("/v3/locations"), json=payload, status=200)

    with pytest.raises(SchemaError, match="OpenAQ response has no results list"):
        client.list_locations(parameters_id=2)


def test_http_error_does_not_disclose_authentication_details(client, responses):
    api_key = client.session.headers["X-API-Key"]
    responses.add(
        responses.GET,
        client.url("/v3/locations"),
        body=api_key,
        status=400,
    )

    with pytest.raises(requests.HTTPError) as exc_info:
        client.list_locations(parameters_id=2)

    message = str(exc_info.value)
    assert api_key not in message
    assert "X-API-Key" not in message
    assert len(responses.calls) == 1


def test_latest_pages_until_a_short_result(client, responses):
    path = "/v3/locations/17/latest"
    responses.add(responses.GET, client.url(path), json=page(2), status=200)
    responses.add(responses.GET, client.url(path), json=page(1), status=200)

    assert len(client.latest(17, limit=2)) == 3
    assert [query(call)["page"] for call in responses.calls] == [["1"], ["2"]]


def test_sensor_hours_pages_and_forwards_interval(client, responses):
    path = "/v3/sensors/23/hours"
    responses.add(responses.GET, client.url(path), json=page(2), status=200)
    responses.add(responses.GET, client.url(path), json=page(1), status=200)

    rows = client.sensor_hours(
        23,
        datetime(2026, 8, 22, tzinfo=UTC),
        datetime(2026, 9, 21, tzinfo=UTC),
        limit=2,
    )

    assert len(rows) == 3
    assert [query(call) for call in responses.calls] == [
        {
            "datetime_from": ["2026-08-22T00:00:00+00:00"],
            "datetime_to": ["2026-09-21T00:00:00+00:00"],
            "limit": ["2"],
            "page": ["1"],
        },
        {
            "datetime_from": ["2026-08-22T00:00:00+00:00"],
            "datetime_to": ["2026-09-21T00:00:00+00:00"],
            "limit": ["2"],
            "page": ["2"],
        },
    ]

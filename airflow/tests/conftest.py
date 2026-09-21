from __future__ import annotations

import sys
from pathlib import Path

import pytest
import responses as responses_module


AIRFLOW_ROOT = Path(__file__).resolve().parents[1]
if str(AIRFLOW_ROOT) not in sys.path:
    sys.path.insert(0, str(AIRFLOW_ROOT))

from pipeline.openaq_client import OpenAQClient


@pytest.fixture
def client() -> OpenAQClient:
    return OpenAQClient(api_key="FAKE_API_KEY_SENTINEL")


@pytest.fixture
def responses():
    with responses_module.RequestsMock() as mock_responses:
        yield mock_responses

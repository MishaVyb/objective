import json
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def scene_update_request_body() -> dict:
    with open(FIXTURES_DIR / "scene_update_request_body.json") as file:
        return json.load(file)

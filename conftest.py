"""
Extend Pytest running settings / plugins.
"""

from enum import StrEnum

import pytest


class Markers(StrEnum):
    postgres = "postgres"
    e2e = "e2e"


def pytest_addoption(parser: pytest.Parser):
    parser.addoption(
        "--settings",
        action="store",
        default=None,
        help="Run test session with custom settings file",
    )
    parser.addoption(
        "--postgres",
        action="store_true",
        default=False,
        help="Run test session against `postgres` database. Define connection in settings file",
    )
    parser.addoption(
        "--alembic",
        action="store_true",
        default=False,
        help="Run test session with alembic migrations",
    )


def pytest_configure(config: pytest.Config):
    # register an additional marker
    config.addinivalue_line(
        "markers",
        f"{Markers.postgres}: mark test to run only if Postgres database is used",
    )
    config.addinivalue_line(
        "markers",
        f"{Markers.e2e}: mark test as end-to-end test against real services",
    )


def pytest_runtest_setup(item: pytest.Function):
    # skip test with `postgres` marker, if no `--postgres` option is provided
    try:
        next(item.iter_markers(name=Markers.postgres))
    except StopIteration:
        return  # no `postgres` marker

    if not item.config.option.postgres:
        pytest.skip(
            "Test marked as `postgres`. Postgres database is required. Use `--postgres` option. ",
        )

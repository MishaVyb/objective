"""
Extend Pytest running settings / plugins.
"""

from enum import StrEnum

import pytest

from tests.helpers import AssertionDifferenceMixin, IsList


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


def pytest_assertrepr_compare(
    config: "Config",
    op: str,
    left: object,
    right: object,
) -> list[str] | None:
    """Return explanation for comparisons in failing assert expressions.

    Return None for no custom explanation, otherwise return a list
    of strings. The strings will be joined by newlines but any newlines
    *in* a string will be escaped. Note that all but the first line will
    be indented slightly, the intention is for the first line to be a summary.

    :param pytest.Config config: The pytest config object.
    """
    if op != "==":
        return None

    # ensure expected IsList for simple lists
    if (
        isinstance(left, list)
        and left
        and isinstance(left[0], AssertionDifferenceMixin)
    ):
        left = IsList(*left)
    if (
        isinstance(right, list)
        and right
        and isinstance(right[0], AssertionDifferenceMixin)
    ):
        right = IsList(*right)

    if isinstance(left, AssertionDifferenceMixin):
        return left.diff_lines(right)
    if isinstance(right, AssertionDifferenceMixin):
        return right.diff_lines(left)

    return None

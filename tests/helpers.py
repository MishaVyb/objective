import difflib
import inspect
import logging
from contextlib import asynccontextmanager
from pprint import pformat
from typing import Any, Callable, Generic, Self, Sequence, TypeVar

import dirty_equals
import pytest
from pydantic import BaseModel
from sqlalchemy import Connection, MetaData, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from alembic.command import downgrade, upgrade
from alembic.config import Config
from app.config import AppSettings, AsyncDatabaseDriver

logger = logging.getLogger(__name__)

########################################################################################
# PARAMETRIZATION
########################################################################################


def _normalize_test_description(v: str, with_underscore: bool = False):
    lines = [l.strip() for l in v.split()]
    v = " ".join(lines)
    if with_underscore:
        v = v.replace(" ", "_").replace(".", "_")
    return v


class Param:
    """Helper to support kwarg values for `pytest.mark.parametrize`."""

    def __init__(
        self,
        id: str | None = None,
        marks: pytest.MarkDecorator | Sequence[pytest.MarkDecorator | pytest.Mark] = (),
        **kwargs,
    ) -> None:
        self.id = _normalize_test_description(id) if id else ""
        self.marks = marks
        self.kwargs = kwargs

    def build_param_id(self, index: int) -> str:
        return f"PARAM_{index}: {self.id}" if self.id else f"PARAM_{index}"

    def construct(self, index: int, keys: list[str]):
        if missing := set(self.kwargs) - set(keys):
            raise ValueError(
                f"Missing arguments: {missing}. "
                "Specify these keys at test function signature as KEYWORD_ONLY arguments. ",
            )
        return pytest.param(
            *[self.kwargs.get(k) for k in keys],
            id=self.build_param_id(index),
            marks=self.marks,
        )


class ParamKwargs:
    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs


class Case(Param):
    group_index: int
    group_summary: str

    def __init__(
        self,
        description: str,
        *,
        marks: pytest.MarkDecorator | Sequence[pytest.MarkDecorator | pytest.Mark] = (),
        kw: ParamKwargs,
    ) -> None:
        return super().__init__(description, marks=marks, **kw.kwargs)

    def build_param_id(self, index: int) -> str:
        return f"CASE_{self.group_index}-{index} ({self.group_summary}): {self.id}"


class CaseGroup:
    def __init__(self, summary: str, *cases: Case) -> None:
        self.summary = summary
        self.cases = cases


class parametrize:
    """Helper decorator factory to support kwarg values for `pytest.mark.parametrize`."""

    def __init__(self, *params: Param) -> None:
        self.params = params

    @classmethod
    def groups(cls, *groups: CaseGroup):
        for i, gr in enumerate(groups):
            for case in gr.cases:
                case.group_index = i + 1
                case.group_summary = gr.summary
        return cls(*[param for gr in groups for param in gr.cases])

    def __call__(self, func: Callable) -> Any:
        sig = inspect.signature(func)
        keys = [
            key
            for key in sig.parameters
            if sig.parameters[key].kind == inspect.Parameter.KEYWORD_ONLY
        ]
        if not keys:
            raise ValueError(
                "Invalid test function signature. "
                "Parametrized arguments should be KEYWORD_ONLY, "
                "when 'POSITIONAL arguments are used for simple fixtures. ",
            )
        params = [p.construct(i + 1, keys) for i, p in enumerate(self.params)]
        return pytest.mark.parametrize(list(keys), params)(func)


########################################################################################
# DIRTY EQUALS
########################################################################################


class AssertionDifferenceMixin:
    def get_operands(self, result: Any):
        ...

    def diff(self, result: dict | BaseModel | Any):
        left, right = self.get_operands(result)
        text = self._get_diff_text(left, right)
        return f"\n{text}\n"

    def diff_lines(self, result: dict | BaseModel | Any):
        left, right = self.get_operands(result)
        return self._get_diff_lines(left, right)

    def _get_diff_lines(self, expected: Any, result: Any):
        expected_lines = pformat(expected).split("\n")
        result_lines = pformat(result).split("\n")
        diff = difflib.ndiff(expected_lines, result_lines)
        return [
            "",
            "========== DIFF ==========",
            *list(diff),
            "",
            "========== EXPECTED ==========",
            *expected_lines,
            "",
            "========== RESULT ==========",
            *result_lines,
        ]

    def _get_diff_text(self, expected: Any, result: Any):
        return "\n".join(self._get_diff_lines(expected, result))


class IsPartialSchema(dirty_equals.IsPartialDict, AssertionDifferenceMixin):
    def equals(self, other: dict | BaseModel) -> bool:
        data = self.use_result(other)
        return super().equals(data)

    def use_result(self, other: dict | BaseModel):
        if not isinstance(other, BaseModel):
            return other
        result_data = other.model_dump()

        # supports for model properties, etc
        for attr in self.expected_values:
            if attr not in other.model_fields:
                try:
                    result_data[attr] = getattr(other, attr)
                except AttributeError:
                    pass

        return result_data

    def get_operands(self, other: dict | BaseModel | Any):
        if isinstance(other, BaseModel):
            other = self.use_result(other)

        elif not isinstance(other, dict):
            return self.expected_values, other

        values = self.expected_values
        if self.partial:
            other = {k: v for k, v in other.items() if k in values}
        if self.ignore:
            values = self._filter_dict(self.expected_values)
            other = self._filter_dict(other)
        return values, other


class _NoItemClass:
    def __repr__(self) -> str:
        return "<NO-ITEM>"


NO_ITEM = _NoItemClass()
ANY_LENGTH: Any = ...
_T = TypeVar("_T")


class IsList(dirty_equals.IsList, Generic[_T], AssertionDifferenceMixin):
    @classmethod
    def build(cls, obj: dirty_equals.IsList | list | None) -> Self | None:
        if obj is None:
            return obj
        return obj if isinstance(obj, cls) else cls(*obj)

    def get_operands(self, right: list | Any):
        left = list(self.items)

        if not isinstance(right, list):
            return left, right

        if not self.check_order:
            try:
                left = sorted(left)
                right = sorted(right)
            except TypeError:
                pass  # FIXME

        if len(left) != len(right):
            left += [NO_ITEM] * (len(right) - len(left))
            right += [NO_ITEM] * (len(left) - len(right))

        if self.positions is None:
            if self.length is None:
                left, right = list(left), list(right)
            else:
                left, right = list(left), list(right[: len(left)])
        else:
            raise NotImplementedError

        l, r = [], []
        for expected_item, result_item in zip(left, right, strict=True):

            if isinstance(expected_item, IsPartialSchema):
                expected_item, result_item = expected_item.get_operands(result_item)

            l.append(expected_item)
            r.append(result_item)

        return l, r


########################################################################################
# DATABASE
########################################################################################


def _quote(clause: Any):
    """Wrap clause into supported by Postgres quotes."""
    return '"' + str(clause) + '"'


async def create_database(
    url: URL | str,
    encoding: str = "utf8",
    template: str = "template1",
):
    url = make_url(url)
    default_postgres = create_async_engine(
        url.set(database="postgres"),
        isolation_level="AUTOCOMMIT",
        echo_pool=False,
        echo=False,
    )
    async with default_postgres.begin() as conn:
        sql = (
            f"CREATE DATABASE {_quote(url.database)} ENCODING '{encoding}' "
            f"TEMPLATE {_quote(template)}"
        )
        await conn.execute(text(sql))
    await default_postgres.dispose()


async def drop_database(url: URL | str):
    url = make_url(url)
    default_postgres = create_async_engine(
        url.set(database="postgres"),
        isolation_level="AUTOCOMMIT",
        echo_pool=False,
        echo=False,
    )
    async with default_postgres.begin() as conn:
        # disconnect all users from the database we are dropping.
        version = conn.dialect.server_version_info
        pid_column = "pid" if (version >= (9, 2)) else "procpid"
        sql = f"""
            SELECT pg_terminate_backend(pg_stat_activity.{pid_column})
            FROM pg_stat_activity
            WHERE pg_stat_activity.datname = '{url.database}'
            AND {pid_column} <> pg_backend_pid();
            """
        await conn.execute(text(sql))

        sql = f"DROP DATABASE {_quote(url.database)}"
        await conn.execute(text(sql))


@asynccontextmanager
async def create_and_drop_tables_by_metadata(engine: AsyncEngine, metadata: MetaData):
    try:
        async with engine.begin() as conn:

            def _run(conn: Connection):
                metadata.create_all(conn, checkfirst=True)

            await conn.run_sync(_run)
        yield
    finally:
        # Tests are using single(!) engine for entire test session,
        # so re-create tables for every single test run to make test data isolated
        async with engine.begin() as conn:
            await conn.run_sync(metadata.drop_all, checkfirst=True)


@asynccontextmanager
async def create_and_drop_tables_by_alembic(engine: AsyncEngine, settings: AppSettings):
    if engine.url.drivername != AsyncDatabaseDriver.POSTGRES:
        pytest.skip(
            "For running alembic migrations on test session, postgres database is required. "
            "Use `--postgres` option. ",
        )

    config = Config(settings.ALEMBIC_INI_PATH)
    config.attributes["app_settings"] = settings

    def _run_upgrade_sync(connection: Connection):
        config.attributes["connection"] = connection
        upgrade(config, "head")

    def _run_downgrade_sync(connection: Connection):
        config.attributes["connection"] = connection
        downgrade(config, "base")

    try:
        async with engine.begin() as conn:
            await conn.run_sync(_run_upgrade_sync)

        yield

    finally:
        async with engine.begin() as conn:
            await conn.run_sync(_run_downgrade_sync)

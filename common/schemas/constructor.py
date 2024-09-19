import inspect
import typing
from typing import ClassVar, Optional, Self, Type, TypedDict, Unpack

import annotated_types
import pydantic
from fastapi import Query
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, PydanticUndefinedAnnotation, ValidationError
from pydantic_core import PydanticUndefined


class _PydanticInitSubclassKwargs(TypedDict):
    exclude: typing.NotRequired[set[str]]
    include: typing.NotRequired[set[str]]
    optional: typing.NotRequired[set[str]]
    required: typing.NotRequired[set[str]]

    # TODO move to separate module/class
    as_query: typing.NotRequired[bool]
    """
    Make schema works as `fastapi.Query` dependency. Usage::

        class Params(BaseModel):
            foo: int | None = None
            bar: str | None = None
            ...

        class _ParamsAsQuery(Params, as_query=True):
            pass

        @app.get("/")
        async def get(

            # NOTE: schema must be specified as Dependency here
            query: Annotated[_ParamsAsQuery, Depends()]
        ):
            ...

    """


def _merge_model_constructor_kwargs(
    parent: _PydanticInitSubclassKwargs,
    child: _PydanticInitSubclassKwargs,
) -> _PydanticInitSubclassKwargs:

    parent = _PydanticInitSubclassKwargs(
        exclude=set(parent.get("exclude", {})),
        include=set(parent.get("include", {})),
        optional=set(parent.get("optional", {})),
        required=set(parent.get("required", {})),
        as_query=parent.get("as_query", False),
    )
    child = _PydanticInitSubclassKwargs(
        exclude=set(child.get("exclude", {})),
        include=set(child.get("include", {})),
        optional=set(child.get("optional", {})),
        required=set(child.get("required", {})),
        as_query=child.get("as_query", False),
    )

    def _merge_exclusive_options(k: str, priority: str):
        # child opposite option take priority over parent
        return child[k] | {f for f in parent[k] if f not in child[priority]}  # type: ignore

    merged = _PydanticInitSubclassKwargs(
        exclude=_merge_exclusive_options("exclude", "include"),
        include=_merge_exclusive_options("include", "exclude"),
        optional=_merge_exclusive_options("optional", "required"),
        required=_merge_exclusive_options("required", "optional"),
        as_query=child["as_query"] or parent["as_query"],
    )

    # omit empty values
    return _PydanticInitSubclassKwargs({k: v for k, v in merged.items() if v})


def _rebuild_model_fields(
    cls: Type[BaseModel],
    *,
    exclude: set[str],
    include: set[str],
    optional: set[str],
    required: set[str],
):
    result_fields = {}
    for fieldname, field in cls.model_fields.items():
        # 'exclude' takes priority over 'include'
        if exclude and fieldname in exclude:
            continue
        if include and fieldname not in include:
            continue

        # 'optional' takes priority over 'required'
        if optional and fieldname in optional:
            if field.is_required():
                field.default = None
                field.annotation = Optional[field.annotation]  # type: ignore
        if required and fieldname in required:
            if not field.is_required():
                field.default = PydanticUndefined
                field.default_factory = None

        result_fields[fieldname] = field

    cls.model_fields = result_fields
    try:
        cls.model_rebuild(force=True)
    except PydanticUndefinedAnnotation:
        # some unresolved ForwardRef annotation found, model_rebuild will be called later
        pass


def _rebuild_model_as_query_dependency(cls: Type[BaseModel]):
    # To make this model works as query Dependency, rebuild class __signature__
    # with parameters where Query is specified as argument default.
    # That new signature will tell FastAPI handle this class as Dependency
    # where each field is Query parameter.

    query_params = []
    for fieldname, field in cls.model_fields.items():

        # Query could be simple Query(None) without any other restrictions
        # because Pydantic will handle all validation later, but it's better
        # to specify the same attributes to build FastAPI openapi properly
        meta_kwargs = {}
        for meta in field.metadata:
            if isinstance(meta, annotated_types.Ge):
                meta_kwargs["ge"] = meta.ge
            elif isinstance(meta, annotated_types.Gt):
                meta_kwargs["gt"] = meta.gt
            elif isinstance(meta, annotated_types.Le):
                meta_kwargs["le"] = meta.le
            elif isinstance(meta, annotated_types.Lt):
                meta_kwargs["lt"] = meta.lt
            elif isinstance(meta, annotated_types.MinLen):
                meta_kwargs["min_length"] = meta.min_length
            elif isinstance(meta, annotated_types.MaxLen):
                meta_kwargs["max_length"] = meta.max_length
            elif isinstance(meta, annotated_types.MultipleOf):
                meta_kwargs["multiple_of"] = meta.multiple_of
            elif isinstance(meta, pydantic.types.Strict):
                meta_kwargs["strict"] = meta.strict
            else:
                raise NotImplementedError(meta)

        query = Query(
            # skipping FastAPi Query defaults at __init__ below, but
            # specify here to complete openapi schema
            default=field.default,
            default_factory=field.default_factory,
            alias=field.alias,
            alias_priority=field.alias_priority,
            validation_alias=field.validation_alias,  # type: ignore
            serialization_alias=field.serialization_alias,
            title=field.title,
            description=field.description,
            json_schema_extra=field.json_schema_extra,  # type: ignore
            **meta_kwargs,  # type: ignore
        )
        param = inspect.Parameter(
            name=fieldname,
            kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
            default=query,
            annotation=field.annotation,
        )
        query_params.append(param)

    # Replace class signature (not cls.__init__ signature)
    # because FastAPI uses class as dependency callable (not its __init__ method).
    # See 'fastapi.dependencies.utils.get_typed_signature'
    cls.__signature__ = inspect.signature(cls).replace(parameters=query_params)


class ModelConstructor(BaseModel):
    """
    Base model with `__init_subclass__` options to build Pydantic schemas with
    comprehensive inheritance. Usage::

        class User(ModelConstructor):
            id: int
            name: str
            email: str

        class UserCreate(User, exclude={"id"}, optional={"email"})
            pass

    Or build schemas as `fastapi.Query` dependency::

        class Params(BaseModel):
            foo: int | None = None
            bar: str | None = None
            ...

        class _ParamsAsQuery(Params, as_query=True):
            pass

        @app.get("/")
        async def get(

            # NOTE: schema must be specified as Dependency here
            query: Annotated[_ParamsAsQuery, Depends()]
        ):
            ...

    And other convenient model instance construct methods: `model_build` and `model_remake`
    """

    __pydantic_init_subclass_kwargs__: ClassVar[_PydanticInitSubclassKwargs]

    @classmethod
    def __init_subclass__(cls, **kwargs: Unpack[_PydanticInitSubclassKwargs]):
        # HACK do nothing, just omit kwargs
        # https://github.com/pydantic/pydantic/issues/6499
        return super().__init_subclass__()

    @classmethod
    def __pydantic_init_subclass__(
        cls,
        **kwargs: Unpack[_PydanticInitSubclassKwargs],
    ):
        super().__pydantic_init_subclass__(**kwargs)

        cls.__pydantic_init_subclass_kwargs__ = kwargs

        # collect init subclass kwargs from mro and merge with current kwargs:

        base_kwargs: _PydanticInitSubclassKwargs = {}
        for child in reversed(cls.__mro__):
            if kw := getattr(child, "__pydantic_init_subclass_kwargs__", None):
                base_kwargs = _merge_model_constructor_kwargs(base_kwargs, kw)

        # validate args:

        kwargs = _merge_model_constructor_kwargs(base_kwargs, kwargs)
        exclude = kwargs.get("exclude", set())
        include = kwargs.get("include", set())
        optional = kwargs.get("optional", set())
        required = kwargs.get("required", set())
        as_query = kwargs.get("as_query", False)

        fieldnames = set(cls.model_fields)
        msg = f"Invalid '{cls.__module__}.{cls.__name__}' declaration. "
        if i := optional & required:
            msg += f"Fields interaction in 'optional' and 'required': {i}"
            raise ValueError(msg)
        if i := exclude - fieldnames:
            msg += f"Invalid fields in 'exclude': {i}"
            raise ValueError(msg)
        if i := include - fieldnames:
            msg += f"Invalid fields in 'include' option: {i}"
            raise ValueError(msg)

        # rebuild model:

        if exclude or include or optional or required:
            _rebuild_model_fields(
                cls,
                exclude=exclude,
                include=include,
                optional=optional,
                required=required,
            )
        if as_query:
            _rebuild_model_as_query_dependency(cls)

    def __init__(self, /, **data):
        as_query = self.__pydantic_init_subclass_kwargs__.get("as_query")
        if as_query:
            # NOTE: workaround to initialize 'model_fields_set' properly.
            # FastAPI always provide field default while initializing Query depends.
            # Omit all auto-populated default values to build self model properly.
            data = {
                k: v
                for k, v in data.items()
                if v != self.model_fields[k].get_default(call_default_factory=True)
            }

        try:
            super().__init__(**data)
        except ValidationError as e:
            if as_query:
                raise RequestValidationError(e.errors())
            __tracebackhide__ = True
            raise e

    @classmethod
    def model_build(
        cls,
        payload: BaseModel | None = None,
        *,
        _payload_exclude: set[str] | None = None,
        _payload_exclude_unset: bool = True,
        _payload_exclude_none: bool = False,
        _payload_exclude_defaults: bool = False,
        **extra_values,
    ) -> Self:
        """
        Construct self from other schema with extra values / overrides.

        :param payload: Reference schema to constrict from.
        :param extra_values: Any extra field values. Not `model_fields` keys are omitted.

        NOTE:
        Includes only fields declared by self model, that satisfy extra='forbid' option.
        But it might include extra fields from **nested** models. To handle extra values
        at nested item (or list of items), `model_build` should be called for each item
        explicitly and provided on top level `model_build` as extra value to override.

        NOTE:
        Pydantic `model_construct` cannot be used in that case, because it omits
        any validation. If nested field passed as dictionary, it won't be transformed
        into a nested model object, that breaks down the whole schema transformation logic.
        """
        extra_values = {k: v for k, v in extra_values.items() if k in cls.model_fields}
        if not payload:
            if not extra_values:
                return None  # type: ignore
            return cls(**extra_values)

        include = set(cls.model_fields)
        if _payload_exclude_unset:
            include = include & payload.model_fields_set
        if _payload_exclude:
            include = [f for f in include if f not in _payload_exclude]

        payload_values = payload.model_dump(
            include=include,
            exclude_none=_payload_exclude_none,
            exclude_defaults=_payload_exclude_defaults,
        )
        data = payload_values | extra_values
        return cls(**data)

    def model_remake(
        self,
        *,
        _self_include: set[str] | None = None,
        _self_exclude: set[str] | None = None,
        _self_exclude_unset: bool = True,
        _self_exclude_none: bool = False,
        _self_exclude_defaults: bool = False,
        **extra_values,
    ) -> Self:
        if missing := set(extra_values) - set(self.model_fields):
            raise ValueError(missing)
        return self.model_validate(
            self.model_dump(
                include=_self_include,
                exclude=_self_exclude,
                exclude_unset=_self_exclude_unset,
                exclude_none=_self_exclude_none,
                exclude_defaults=_self_exclude_defaults,
            )
            | extra_values,
        )

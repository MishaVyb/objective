import importlib
import sys
import traceback
from typing import Any

from mypy.plugin import ClassDefContext
from mypy.util import FancyFormatter
from pydantic.mypy import (
    ModelConfigData,
    PydanticModelClassVar,
    PydanticModelField,
    PydanticModelTransformer,
    PydanticPlugin,
)

from common.schemas.constructor import ModelConstructor

# Increment version if plugin changes and mypy caches should be invalidated
__version__ = 2


def plugin(version: str) -> type[PydanticPlugin]:
    return ExtendedPydanticPlugin


class ExtendedPydanticPlugin(PydanticPlugin):
    """
    Extend original `pydantic.plugin` according to `ModelConstructor` options.
    Usage::

        [tool.mypy]
        plugins = "saber.lib.pydantic.mypy"

    """

    def _pydantic_model_class_maker_callback(self, ctx: ClassDefContext) -> bool:
        transformer = ExtendedPydanticModelTransformer(
            ctx.cls,
            ctx.reason,
            ctx.api,
            self.plugin_config,
        )
        return transformer.transform()


class ExtendedPydanticModelTransformer(PydanticModelTransformer):
    def collect_fields_and_class_vars(
        self,
        model_config: ModelConfigData,
        is_root_model: bool,
    ) -> tuple[list[PydanticModelField] | None, list[PydanticModelClassVar] | None]:
        """Modify model fields defined by `pydantic.plugin` depending on `ModelConstructor` options."""

        fields, class_vars = super().collect_fields_and_class_vars(
            model_config,
            is_root_model,
        )
        if not fields:
            return fields, class_vars

        class_def = self._cls
        for base_info in reversed(class_def.info.mro):
            if (
                ModelConstructor.__module__ == base_info.module_name
                and ModelConstructor.__name__ == base_info.name
            ):
                break
        else:
            return fields, class_vars

        # NOTE
        # handle ModelConstructor options by importing target model definition:
        module_name = class_def.info.module_name
        try:
            module = importlib.import_module(module_name)
        except Exception:
            formatter = FancyFormatter(sys.stdout, sys.stderr, hide_error_codes=False)
            msgs = [
                formatter.style("WARNING \n", color="yellow"),
                "Can not invalidate model declaration for %s. "
                % formatter.style(class_def.fullname, color="blue"),
                "Fails on importing class definition: \n%s"
                % formatter.style(traceback.format_exc(-3), color="none"),
                formatter.style(
                    "Fallbacks to default 'pydantic.mypy' plugin behavior. \n\n",
                    color="yellow",
                ),
            ]
            sys.stdout.write("".join(msgs))
            return fields, class_vars

        # NOTE
        # Resolve getting object from globals and/or from any object locals
        # For example, resolve this fullname: 'src.app.schemas.MySchema.NestedSchema'
        entity = module
        entity_names = class_def.info.fullname.split(".")
        for name in entity_names:
            if name not in module_name:
                entity = getattr(entity, name, None)
        model: Any = entity

        if not isinstance(model, type) or not issubclass(model, ModelConstructor):
            return fields, class_vars

        result_fields = []
        for field_info in fields:

            # omit fields which doesn't belong to model ('exclude/include' option)
            if field := model.model_fields.get(field_info.name):

                # field was marked as 'optional'
                if not field.is_required() and not field_info.has_default:
                    field_info = PydanticModelField(
                        name=field_info.name,
                        alias=field_info.alias,
                        has_dynamic_alias=field_info.has_dynamic_alias,
                        has_default=True,
                        line=field_info.line,
                        column=field_info.column,
                        type=field_info.type,
                        info=field_info.info,
                    )

                # field was marked as 'required'
                elif field.is_required() and field_info.has_default:
                    field_info = PydanticModelField(
                        name=field_info.name,
                        alias=field_info.alias,
                        has_dynamic_alias=field_info.has_dynamic_alias,
                        has_default=False,
                        line=field_info.line,
                        column=field_info.column,
                        type=field_info.type,
                        info=field_info.info,
                    )

                result_fields.append(field_info)

        return result_fields, class_vars

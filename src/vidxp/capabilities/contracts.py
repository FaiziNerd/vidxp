from __future__ import annotations

from importlib import import_module
from types import MappingProxyType
from typing import Any, Callable, Mapping

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    NonNegativeFloat,
    field_validator,
    model_validator,
)

from vidxp.core.contracts import IndexConfig, VideoSource
from vidxp.core.indexing_common import ProgressCallback


class _ContractModel(BaseModel):
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        extra="forbid",
        frozen=True,
    )


class CapabilityInput(BaseModel):
    """Base model for validated capability input."""

    model_config = ConfigDict(extra="forbid")


class CapabilityOutput(_ContractModel):
    """Base model for validated capability output."""


class CapabilityConfig(_ContractModel):
    """Base model for settings owned and validated by one capability."""


class RuntimeDependency(_ContractModel):
    """One import or executable required by a capability."""

    label: str = Field(min_length=1)
    distribution: str | None = None
    module: str | None = None
    check: Callable[[], str | None] | None = None

    def inspect(self) -> dict[str, Any]:
        try:
            if self.module is not None:
                import_module(self.module)
            detail = self.check() if self.check is not None else None
        except Exception as exc:
            return {
                "name": self.label,
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}",
            }
        result: dict[str, Any] = {
            "name": self.label,
            "ok": True,
            "error": None,
        }
        if detail is not None:
            result["path"] = detail
        return result


class CapabilityContext(_ContractModel):
    """Runtime context shared by transport-neutral capability operations."""

    config: IndexConfig | None

    def require_config(self) -> IndexConfig:
        if self.config is None:
            raise RuntimeError("This operation requires an active index.")
        return self.config


class PreparationContext(_ContractModel):
    """Runtime values supplied to one capability's preparation hook."""

    device: str = Field(min_length=1)
    settings: CapabilityConfig


OperationHandler = Callable[[CapabilityContext, BaseModel], BaseModel | Mapping]


class OperationDefinition(_ContractModel):
    """Validated input, output, and implementation for one operation."""

    input_model: type[BaseModel]
    output_model: type[BaseModel]
    handler: OperationHandler
    requires_index: bool = True

    @field_validator("input_model", "output_model")
    @classmethod
    def _require_model(
        cls,
        value: type[BaseModel],
    ) -> type[BaseModel]:
        if not isinstance(value, type) or not issubclass(value, BaseModel):
            raise ValueError("Operation schemas must be Pydantic models.")
        return value

    def invoke(
        self,
        context: CapabilityContext,
        payload: BaseModel | Mapping[str, Any],
    ) -> BaseModel:
        request = self.input_model.model_validate(payload)
        result = self.handler(context, request)
        return self.output_model.model_validate(result)


class CapabilityIndexResult(_ContractModel):
    """Summary and timing data returned by an indexing handler."""

    summary: dict[str, Any]
    timings: dict[str, NonNegativeFloat] = Field(default_factory=dict)


IndexHandler = Callable[..., CapabilityIndexResult]
PrepareHandler = Callable[
    [PreparationContext, ProgressCallback | None],
    tuple[str, ...],
]
DependencySelector = Callable[
    [VideoSource],
    tuple[RuntimeDependency, ...],
]
ModelManifest = Callable[
    [IndexConfig, tuple[VideoSource, ...]],
    Mapping[str, Any],
]
CLIFactory = Callable[[], Any]


class CapabilityDefinition(_ContractModel):
    """Everything the application needs to run one named capability."""

    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    extra: str = Field(min_length=1)
    config_model: type[CapabilityConfig] = CapabilityConfig
    dependencies: tuple[RuntimeDependency, ...] = ()
    collection_name: str | None = None
    indexer: IndexHandler | None = None
    index_processor: Any | None = None
    index_stage: str | None = None
    operations: Mapping[str, OperationDefinition] = Field(default_factory=dict)
    dependencies_for_source: DependencySelector | None = None
    prepare: PrepareHandler | None = None
    model_manifest: ModelManifest | None = None
    cli_name: str | None = None
    cli_factory: CLIFactory | None = None

    @field_validator("config_model")
    @classmethod
    def _require_config_model(
        cls,
        value: type[CapabilityConfig],
    ) -> type[CapabilityConfig]:
        if (
            not isinstance(value, type)
            or not issubclass(value, CapabilityConfig)
        ):
            raise ValueError(
                "Capability config_model must extend CapabilityConfig."
            )
        return value

    @field_validator("operations")
    @classmethod
    def _freeze_operations(
        cls,
        value: Mapping[str, OperationDefinition],
    ) -> Mapping[str, OperationDefinition]:
        return MappingProxyType(dict(value))

    @model_validator(mode="after")
    def _require_complete_integrations(self) -> CapabilityDefinition:
        indexing_fields = (
            self.collection_name,
            self.indexer,
            self.index_stage,
        )
        if any(value is not None for value in indexing_fields) and not all(
            value is not None for value in indexing_fields
        ):
            raise ValueError(
                "Indexable capabilities must declare collection names, "
                "an indexer, and an index stage together."
            )
        if (self.cli_name is None) != (self.cli_factory is None):
            raise ValueError(
                "cli_name and cli_factory must either both be set or both be unset."
            )
        if self.indexer is None and not self.operations:
            raise ValueError(
                "A capability must provide an indexer or at least one operation."
            )
        return self

    def source_dependencies(
        self,
        source: VideoSource,
    ) -> tuple[RuntimeDependency, ...]:
        if self.dependencies_for_source is None:
            return self.dependencies
        return self.dependencies_for_source(source)


def capability_install_hint(name: str) -> str:
    return f'Install the capability with: pip install "vidxp[{name}]"'

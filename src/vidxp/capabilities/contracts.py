from __future__ import annotations

from dataclasses import dataclass, field
from importlib import import_module
from types import MappingProxyType
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Mapping,
)

from pydantic import BaseModel

if TYPE_CHECKING:
    from vidxp.core.contracts import IndexConfig, VideoSource
    from vidxp.core.indexing_common import ProgressCallback


class CapabilityInput(BaseModel):
    """Base model for validated capability input."""

    model_config = {"extra": "forbid"}


class CapabilityOutput(BaseModel):
    """Base model for validated capability output."""

    model_config = {"extra": "forbid", "frozen": True}


class CapabilityConfig(BaseModel):
    """Base model for settings owned and validated by one capability."""

    model_config = {"extra": "forbid", "frozen": True}


@dataclass(frozen=True)
class RuntimeDependency:
    """One import or executable required by a capability."""

    label: str
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


@dataclass(frozen=True)
class CapabilityContext:
    """Runtime context shared by transport-neutral capability operations."""

    config: IndexConfig | None

    def require_config(self) -> IndexConfig:
        if self.config is None:
            raise RuntimeError("This operation requires an active index.")
        return self.config


OperationHandler = Callable[[CapabilityContext, BaseModel], BaseModel | Mapping]


@dataclass(frozen=True)
class OperationDefinition:
    """Validated input, output, and implementation for one operation."""

    input_model: type[BaseModel]
    output_model: type[BaseModel]
    handler: OperationHandler
    requires_index: bool = True

    def invoke(
        self,
        context: CapabilityContext,
        payload: BaseModel | Mapping[str, Any],
    ) -> BaseModel:
        request = self.input_model.model_validate(payload)
        result = self.handler(context, request)
        return self.output_model.model_validate(result)


@dataclass(frozen=True)
class CapabilityIndexResult:
    """Summary and timing data returned by an indexing handler."""

    summary: Mapping[str, Any]
    timings: Mapping[str, float] = field(default_factory=dict)


IndexHandler = Callable[..., CapabilityIndexResult]
PrepareHandler = Callable[
    ["IndexConfig", str | None, "ProgressCallback | None"],
    tuple[str, ...],
]
DependencySelector = Callable[
    ["VideoSource"],
    tuple[RuntimeDependency, ...],
]
ModelManifest = Callable[
    ["IndexConfig", tuple["VideoSource", ...]],
    Mapping[str, Any],
]
CLIFactory = Callable[[], Any]


@dataclass(frozen=True)
class CapabilityDefinition:
    """Everything the application needs to run one named capability."""

    name: str
    description: str
    extra: str
    config_model: type[CapabilityConfig] = CapabilityConfig
    dependencies: tuple[RuntimeDependency, ...] = ()
    collection_name: str | None = None
    indexer: IndexHandler | None = None
    index_stage: str | None = None
    operations: Mapping[str, OperationDefinition] = field(default_factory=dict)
    dependencies_for_source: DependencySelector | None = None
    prepare: PrepareHandler | None = None
    model_manifest: ModelManifest | None = None
    cli_name: str | None = None
    cli_factory: CLIFactory | None = None

    def __post_init__(self) -> None:
        for label, value in (
            ("name", self.name),
            ("description", self.description),
            ("extra", self.extra),
        ):
            if not str(value).strip():
                raise ValueError(f"Capability {label} must not be empty.")
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
        object.__setattr__(
            self,
            "operations",
            MappingProxyType(dict(self.operations)),
        )

    def source_dependencies(
        self,
        source: VideoSource,
    ) -> tuple[RuntimeDependency, ...]:
        if self.dependencies_for_source is None:
            return self.dependencies
        return self.dependencies_for_source(source)


def capability_install_hint(name: str) -> str:
    return f'Install the capability with: pip install "vidxp[{name}]"'

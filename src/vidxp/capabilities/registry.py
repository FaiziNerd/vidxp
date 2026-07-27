from __future__ import annotations

from types import MappingProxyType
from typing import Any, Iterable, Mapping

from vidxp.capabilities.actor.definition import DEFINITION as ACTOR
from vidxp.capabilities.contracts import (
    CapabilityDefinition,
    RuntimeDependency,
    capability_install_hint,
)
from vidxp.capabilities.dialogue.definition import DEFINITION as DIALOGUE
from vidxp.capabilities.scene.definition import DEFINITION as SCENE
from vidxp.core.contracts import VideoSource


_BUILT_INS = (DIALOGUE, SCENE, ACTOR)
CAPABILITIES = MappingProxyType(
    {capability.name: capability for capability in _BUILT_INS}
)

if len(CAPABILITIES) != len(_BUILT_INS):
    raise RuntimeError("Capability names must be unique.")


def capability_names() -> tuple[str, ...]:
    return tuple(CAPABILITIES)


def index_capability_names() -> tuple[str, ...]:
    return tuple(
        name
        for name, capability in CAPABILITIES.items()
        if capability.indexer is not None
    )


def get_capability(name: str) -> CapabilityDefinition:
    try:
        return CAPABILITIES[name]
    except KeyError as exc:
        available = ", ".join(capability_names())
        raise ValueError(
            f"Unknown capability {name!r}. Available capabilities: {available}."
        ) from exc


def validate_capability_names(names: Iterable[str]) -> tuple[str, ...]:
    selected = tuple(dict.fromkeys(str(name).strip() for name in names))
    if not selected:
        raise ValueError("At least one capability is required.")
    for name in selected:
        get_capability(name)
    return selected


def collection_names(
    names: Iterable[str] | None = None,
) -> dict[str, str]:
    selected = (
        index_capability_names()
        if names is None
        else validate_capability_names(names)
    )
    return {
        name: get_capability(name).collection_name
        for name in selected
        if get_capability(name).indexer is not None
    }


def validate_capability_options(
    names: Iterable[str],
    options: Mapping[str, Mapping[str, Any]] | None,
) -> dict[str, dict[str, Any]]:
    selected = validate_capability_names(names)
    supplied = dict(options or {})
    unknown = sorted(set(supplied) - set(selected))
    if unknown:
        raise ValueError(
            "Options were supplied for disabled capabilities: "
            + ", ".join(unknown)
        )
    return {
        name: get_capability(name)
        .config_model.model_validate(supplied.get(name, {}))
        .model_dump(mode="python")
        for name in selected
    }


def dependencies_for(
    names: Iterable[str],
    *,
    source: VideoSource | None = None,
) -> tuple[RuntimeDependency, ...]:
    dependencies = []
    for name in validate_capability_names(names):
        capability = get_capability(name)
        dependencies.extend(
            capability.dependencies
            if source is None
            else capability.source_dependencies(source)
        )
    unique = {}
    for dependency in dependencies:
        key = (
            dependency.module,
            dependency.distribution,
            dependency.label,
        )
        unique.setdefault(key, dependency)
    return tuple(unique.values())


def dependency_checks(names: Iterable[str]) -> tuple[dict, ...]:
    return tuple(
        dependency.inspect()
        for dependency in dependencies_for(names)
    )


def require_dependencies(
    names: Iterable[str],
    *,
    source: VideoSource,
) -> None:
    selected = validate_capability_names(names)
    failures = [
        result
        for dependency in dependencies_for(selected, source=source)
        if not (result := dependency.inspect())["ok"]
    ]
    if failures:
        details = "; ".join(
            f"{failure['name']}: {failure['error']}"
            for failure in failures
        )
        extras = ",".join(
            get_capability(name).extra for name in selected
        )
        raise RuntimeError(
            f"Capability dependencies are unavailable: {details}. "
            + capability_install_hint(extras)
        )


def runtime_distributions() -> tuple[str, ...]:
    distributions = {
        dependency.distribution
        for capability in CAPABILITIES.values()
        for dependency in capability.dependencies
        if dependency.distribution is not None
    }
    distributions.update({"filelock", "pydantic", "rich", "typer"})
    return tuple(sorted(distributions, key=str.lower))

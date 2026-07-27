from __future__ import annotations

from types import MappingProxyType
from typing import Any, Iterable, Mapping

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

from vidxp.capabilities.actor.definition import DEFINITION as ACTOR
from vidxp.capabilities.contracts import (
    CapabilityDefinition,
    RuntimeCheck,
    capability_install_hint,
)
from vidxp.capabilities.dialogue.definition import DEFINITION as DIALOGUE
from vidxp.capabilities.scene.definition import DEFINITION as SCENE
from vidxp.core.contracts import VideoSource
from vidxp.dependencies import (
    active_requirements,
    inspect_requirement,
    installed_base_requirements,
    packaged_requirements,
)


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


def preparable_capability_names() -> tuple[str, ...]:
    return tuple(
        name
        for name, capability in CAPABILITIES.items()
        if capability.prepare is not None
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


def requirements_for(
    names: Iterable[str],
    *,
    source: VideoSource | None = None,
) -> tuple[Requirement, ...]:
    requirements = []
    for name in validate_capability_names(names):
        capability = get_capability(name)
        selected = active_requirements(
            packaged_requirements(f"vidxp.capabilities.{name}")
        )
        requirements.extend(
            selected
            if source is None
            else capability.source_requirements(source, selected)
        )
    unique = {str(requirement): requirement for requirement in requirements}
    return tuple(unique.values())


def runtime_checks_for(
    names: Iterable[str],
    *,
    source: VideoSource | None = None,
) -> tuple[RuntimeCheck, ...]:
    checks = (
        check
        for name in validate_capability_names(names)
        for check in get_capability(name).runtime_checks
        if check.applies(source)
    )
    return tuple({check.label: check for check in checks}.values())


def dependency_checks(names: Iterable[str]) -> tuple[dict, ...]:
    return tuple(
        inspect_requirement(requirement)
        for requirement in requirements_for(names)
    ) + tuple(
        check.inspect()
        for check in runtime_checks_for(names)
    )


def require_dependencies(
    names: Iterable[str],
    *,
    source: VideoSource,
) -> None:
    selected = validate_capability_names(names)
    failures = [
        result
        for requirement in requirements_for(selected, source=source)
        if not (result := inspect_requirement(requirement))["ok"]
    ]
    failures.extend(
        result
        for check in runtime_checks_for(selected, source=source)
        if not (result := check.inspect())["ok"]
    )
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
        canonicalize_name(requirement.name)
        for requirement in installed_base_requirements()
    }
    distributions.update(
        canonicalize_name(requirement.name)
        for requirement in requirements_for(capability_names())
    )
    return tuple(sorted(distributions, key=str.lower))

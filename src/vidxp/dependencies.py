from __future__ import annotations

from functools import lru_cache
from importlib.metadata import (
    PackageNotFoundError,
    requires as distribution_requirements,
    version,
)
from importlib.resources import files
from typing import Iterable

from packaging.requirements import Requirement


@lru_cache(maxsize=None)
def packaged_requirements(
    package: str,
    resource: str = "requirements.txt",
) -> tuple[Requirement, ...]:
    content = files(package).joinpath(resource).read_text(
        encoding="utf-8"
    )
    return tuple(
        Requirement(line)
        for raw_line in content.splitlines()
        if (line := raw_line.strip()) and not line.startswith("#")
    )


def active_requirements(
    requirements: Iterable[Requirement],
    *,
    extra: str = "",
) -> tuple[Requirement, ...]:
    environment = {"extra": extra}
    return tuple(
        requirement
        for requirement in requirements
        if requirement.marker is None
        or requirement.marker.evaluate(environment)
    )


def inspect_requirement(requirement: Requirement) -> dict:
    try:
        installed = version(requirement.name)
    except PackageNotFoundError:
        return {
            "name": requirement.name,
            "requirement": str(requirement),
            "installed_version": None,
            "ok": False,
            "error": "distribution is not installed",
        }
    if requirement.specifier and not requirement.specifier.contains(
        installed,
        prereleases=True,
    ):
        return {
            "name": requirement.name,
            "requirement": str(requirement),
            "installed_version": installed,
            "ok": False,
            "error": (
                f"installed version {installed} does not satisfy "
                f"{requirement.specifier}"
            ),
        }
    return {
        "name": requirement.name,
        "requirement": str(requirement),
        "installed_version": installed,
        "ok": True,
        "error": None,
    }


def requirements_available(package: str) -> bool:
    return all(
        inspect_requirement(requirement)["ok"]
        for requirement in active_requirements(
            packaged_requirements(package)
        )
    )


def installed_base_requirements(
    distribution: str = "vidxp",
) -> tuple[Requirement, ...]:
    try:
        declared = distribution_requirements(distribution) or ()
    except PackageNotFoundError:
        return ()
    return active_requirements(
        (Requirement(value) for value in declared),
    )

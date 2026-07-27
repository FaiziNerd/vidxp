from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from vidxp.cli_support import (
    OutputFormat,
    effective_output_format,
    emit_json,
    state_from_context,
)


app = typer.Typer(
    no_args_is_help=True,
    help="Manage named index repositories.",
)


def _emit_repository(
    repository,
    *,
    output_format: OutputFormat,
) -> None:
    payload = repository.to_dict()
    if output_format == OutputFormat.json:
        emit_json(payload)
        return
    table = Table(title=f"Repository {repository.name}")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("Index directory", str(repository.index_directory))
    table.add_row("Device", repository.device or "default")
    table.add_row("Configured", "yes" if repository.configured else "no")
    Console().print(table)


@app.command("list")
def repositories_list(
    ctx: typer.Context,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit machine-readable JSON."),
    ] = False,
) -> None:
    """List configured repositories and the active selection."""

    state = state_from_context(ctx)
    repositories = state.registry.list()
    payload = {
        "active_repository": state.repository.name,
        "config_file": str(state.registry.path),
        "repositories": [item.to_dict() for item in repositories],
    }
    if effective_output_format(state, json_output) == OutputFormat.json:
        emit_json(payload)
        return
    table = Table(title="VidXP repositories")
    table.add_column("Active")
    table.add_column("Name")
    table.add_column("Index directory")
    table.add_column("Device")
    for repository in repositories:
        table.add_row(
            "*" if repository.name == state.repository.name else "",
            repository.name,
            str(repository.index_directory),
            repository.device or "default",
        )
    Console().print(table)


@app.command("show")
def repositories_show(
    ctx: typer.Context,
    name: Annotated[
        str | None,
        typer.Argument(help="Repository name; defaults to the active one."),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit machine-readable JSON."),
    ] = False,
) -> None:
    """Show one repository configuration."""

    state = state_from_context(ctx)
    repository = (
        state.registry.resolve(name)
        if name is not None
        else state.repository
    )
    _emit_repository(
        repository,
        output_format=effective_output_format(state, json_output),
    )


@app.command("add")
def repositories_add(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Repository name.")],
    index_directory: Annotated[
        Path,
        typer.Option(
            "--index-dir",
            file_okay=False,
            help="Local index directory managed by this repository.",
        ),
    ],
    device: Annotated[
        str | None,
        typer.Option("--device", help="Optional repository device."),
    ] = None,
    replace: Annotated[
        bool,
        typer.Option("--replace", help="Replace an existing configuration."),
    ] = False,
    use: Annotated[
        bool,
        typer.Option("--use", help="Make this repository active."),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit machine-readable JSON."),
    ] = False,
) -> None:
    """Add or replace a named local index repository."""

    state = state_from_context(ctx)
    repository = state.registry.add(
        name,
        index_directory,
        device=device,
        replace=replace,
    )
    if use:
        repository = state.registry.use(repository.name)
    _emit_repository(
        repository,
        output_format=effective_output_format(state, json_output),
    )


@app.command("use")
def repositories_use(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Repository name.")],
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit machine-readable JSON."),
    ] = False,
) -> None:
    """Select the default repository for future commands."""

    state = state_from_context(ctx)
    repository = state.registry.use(name)
    _emit_repository(
        repository,
        output_format=effective_output_format(state, json_output),
    )


@app.command("remove")
def repositories_remove(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Repository name.")],
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Skip the confirmation prompt."),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Emit machine-readable JSON."),
    ] = False,
) -> None:
    """Remove configuration without deleting indexed data."""

    state = state_from_context(ctx)
    repository = state.registry.resolve(name)
    if not repository.configured:
        raise typer.BadParameter(
            "The implicit default repository has no saved configuration."
        )
    if not yes:
        typer.confirm(
            f"Remove repository configuration {repository.name!r}? "
            "Indexed data will not be deleted.",
            abort=True,
        )
    removed = state.registry.remove(repository.name)
    payload = {
        "removed": removed.to_dict(),
        "index_deleted": False,
    }
    if effective_output_format(state, json_output) == OutputFormat.json:
        emit_json(payload)
    else:
        typer.echo(
            f"Removed {removed.name!r}; indexed data was left untouched."
        )

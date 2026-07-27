from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Annotated

import typer

from vidxp import __version__
from vidxp.application import VidXPService
from vidxp.benchmarks.cli import app as benchmark_app
from vidxp.capabilities.actor.results import ActorClusterNotFoundError
from vidxp.capabilities.registry import CAPABILITIES
from vidxp.cli_commands.index import app as index_app
from vidxp.cli_commands.repositories import app as repositories_app
from vidxp.cli_commands.runtime import doctor, prepare, ui
from vidxp.cli_commands.search import app as search_app
from vidxp.cli_support import CLIState, OutputFormat
from vidxp.core.contracts import IndexSchemaError
from vidxp.index_state import (
    IndexingInProgressError,
    IndexNotReadyError,
)
from vidxp.repositories import resolve_repository


app = typer.Typer(
    no_args_is_help=True,
    help="Index and search video with installable capabilities.",
)
app.add_typer(index_app, name="index")
app.add_typer(search_app, name="search")
app.add_typer(repositories_app, name="repositories")
app.add_typer(benchmark_app, name="benchmark")
for _capability in CAPABILITIES.values():
    if _capability.cli_factory is not None:
        app.add_typer(
            _capability.cli_factory(),
            name=_capability.cli_name,
        )
app.command()(doctor)
app.command()(prepare)
app.command()(ui)


def _show_version(value: bool) -> None:
    if value:
        typer.echo(f"VidXP {__version__}")
        raise typer.Exit()


@app.callback()
def app_options(
    ctx: typer.Context,
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            "-V",
            callback=_show_version,
            is_eager=True,
            help="Show the installed VidXP version and exit.",
        ),
    ] = False,
    repository_name: Annotated[
        str | None,
        typer.Option(
            "--repository",
            "-r",
            help="Named repository to use.",
        ),
    ] = None,
    config_file: Annotated[
        Path | None,
        typer.Option(
            "--config",
            dir_okay=False,
            help="Repository configuration file.",
        ),
    ] = None,
    index_directory: Annotated[
        Path | None,
        typer.Option(
            "--index-dir",
            file_okay=False,
            help="Override the selected repository index directory.",
        ),
    ] = None,
    device: Annotated[
        str | None,
        typer.Option(
            "--device",
            help="Override the selected repository runtime device.",
        ),
    ] = None,
    output_format: Annotated[
        OutputFormat,
        typer.Option(
            "--format",
            envvar="VIDXP_OUTPUT_FORMAT",
            help="Default command output format.",
        ),
    ] = OutputFormat.rich,
    quiet: Annotated[
        bool,
        typer.Option("--quiet", "-q", help="Suppress progress output."),
    ] = False,
) -> None:
    registry, repository = resolve_repository(
        registry_path=config_file,
        name=repository_name,
        index_directory=index_directory,
        device=device,
    )
    ctx.obj = CLIState(
        service=VidXPService(
            repository.index_directory,
            device=repository.device,
        ),
        registry=registry,
        repository=repository,
        output_format=output_format,
        quiet=quiet,
    )


def _wants_json(arguments: list[str] | None = None) -> bool:
    values = list(sys.argv[1:] if arguments is None else arguments)
    if "--json" in values:
        return True
    for index, value in enumerate(values):
        if value == "--format" and index + 1 < len(values):
            return values[index + 1].lower() == "json"
        if value.startswith("--format="):
            return value.split("=", 1)[1].lower() == "json"
    return os.environ.get("VIDXP_OUTPUT_FORMAT", "").lower() == "json"


def _error_message(exc: Exception) -> str:
    formatter = getattr(exc, "format_message", None)
    return str(formatter()) if formatter is not None else str(exc)


def _exit_code(exc: Exception) -> int:
    return int(getattr(exc, "exit_code", 1) or 1)


def _emit_error(exc: Exception, *, json_output: bool) -> None:
    message = _error_message(exc)
    if json_output:
        typer.echo(
            json.dumps(
                {
                    "ok": False,
                    "error": {
                        "type": type(exc).__name__,
                        "message": message,
                        "exit_code": _exit_code(exc),
                    },
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ),
            err=True,
        )
    elif show := getattr(exc, "show", None):
        show(file=sys.stderr)
    else:
        typer.secho(message, fg=typer.colors.RED, err=True)


def main() -> None:
    try:
        app(standalone_mode=False)
    except typer.Exit as exc:
        raise SystemExit(exc.exit_code) from None
    except typer.Abort as exc:
        _emit_error(exc, json_output=_wants_json())
        raise SystemExit(1) from exc
    except Exception as exc:
        is_command_error = hasattr(exc, "exit_code") and hasattr(
            exc,
            "format_message",
        )
        is_expected_runtime_error = isinstance(
            exc,
            (
                ActorClusterNotFoundError,
                FileNotFoundError,
                IndexNotReadyError,
                IndexingInProgressError,
                IndexSchemaError,
                RuntimeError,
                ValueError,
            ),
        )
        if not is_command_error and not is_expected_runtime_error:
            raise
        _emit_error(exc, json_output=_wants_json())
        raise SystemExit(_exit_code(exc)) from exc


if __name__ == "__main__":
    main()

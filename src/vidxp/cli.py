from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from vidxp import __version__
from vidxp.application import VidXPService
from vidxp.benchmarks.cli import app as benchmark_app
from vidxp.cli_commands import compat
from vidxp.cli_commands.actors import app as actors_app
from vidxp.cli_commands.index import app as index_app
from vidxp.cli_commands.runtime import doctor, prepare
from vidxp.cli_commands.search import app as search_app
from vidxp.cli_support import CLIState, OutputFormat
from vidxp.core.actor_results import ActorClusterNotFoundError
from vidxp.core.contracts import IndexSchemaError
from vidxp.index_state import (
    IndexingInProgressError,
    IndexNotReadyError,
)


app = typer.Typer(
    no_args_is_help=True,
    help="Index and search video by dialogue, scene, and actor.",
)
app.add_typer(index_app, name="index")
app.add_typer(search_app, name="search")
app.add_typer(actors_app, name="actors")
app.add_typer(benchmark_app, name="benchmark")
app.command()(doctor)
app.command()(prepare)
app.command("videoindex", hidden=True, deprecated=True)(compat.videoindex)
app.command("dialogue", hidden=True, deprecated=True)(compat.dialogue)
app.command("scene", hidden=True, deprecated=True)(compat.scene)
app.command("actor", hidden=True, deprecated=True)(compat.actor)


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
    index_directory: Annotated[
        Path,
        typer.Option(
            "--index-dir",
            envvar="VIDXP_INDEX_DIR",
            file_okay=False,
            help="Local index directory.",
        ),
    ] = Path("chroma_data"),
    device: Annotated[
        str | None,
        typer.Option(
            "--device",
            envvar="VIDXP_DEVICE",
            help="Runtime device override, for example cpu, cuda, or mps.",
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
    ctx.obj = CLIState(
        service=VidXPService(index_directory, device=device),
        output_format=output_format,
        quiet=quiet,
    )


def main() -> None:
    try:
        app()
    except (
        ActorClusterNotFoundError,
        FileNotFoundError,
        IndexNotReadyError,
        IndexingInProgressError,
        IndexSchemaError,
        ValueError,
    ) as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()

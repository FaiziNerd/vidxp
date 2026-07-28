from __future__ import annotations

from typing import Annotated, Callable

import typer

from vidxp.capabilities.registry import CAPABILITIES
from vidxp.capabilities.schemas import SearchResult
from vidxp.cli_support import (
    CLIState,
    effective_output_format,
    emit_search,
    state_from_context,
)


app = typer.Typer(no_args_is_help=True, help="Search the active index.")


def run_search(
    state: CLIState,
    capability: str,
    query: str,
    *,
    top_k: int,
    json_output: bool,
) -> SearchResult:
    result = state.service.search(capability, query, top_k=top_k)
    emit_search(
        result,
        output_format=effective_output_format(state, json_output),
    )
    return result


def _search_command(capability: str) -> Callable:
    def command(
        ctx: typer.Context,
        query: Annotated[
            str,
            typer.Argument(help="Text query to find."),
        ],
        top_k: Annotated[
            int,
            typer.Option(
                "--top-k",
                "-k",
                min=1,
                help="Maximum ranked hits.",
            ),
        ] = 10,
        json_output: Annotated[
            bool,
            typer.Option("--json", help="Emit machine-readable JSON."),
        ] = False,
    ) -> None:
        run_search(
            state_from_context(ctx),
            capability,
            query,
            top_k=top_k,
            json_output=json_output,
        )

    command.__name__ = f"search_{capability}"
    command.__doc__ = CAPABILITIES[capability].description
    return command


for _name, _capability in CAPABILITIES.items():
    if "search" in _capability.operations:
        app.command(_name)(_search_command(_name))

from __future__ import annotations

from typing import Annotated

import typer
from rich import print

from vidxp.core.actor_results import (
    ActorClusterNotFoundError,
    render_actor_result,
)
from vidxp.core.contracts import IndexConfig, IndexSchemaError
from vidxp.core.models import (
    INDEXING_DEPENDENCIES,
    dependency_failures,
    get_alignment_model,
    get_clip_model,
    get_embedder,
    get_whisper_model,
)
from vidxp.core.runner import (
    index_video,
    local_config_from_status,
)
from vidxp.core.search import search_dialogue, search_scene
from vidxp.core.video import ffmpeg_binary
from vidxp.index_state import (
    IndexingInProgressError,
    IndexNotReadyError,
    require_ready_index,
)


app = typer.Typer()


def _modalities(value: str) -> tuple[str, ...]:
    modalities = tuple(
        item.strip().lower()
        for item in value.split(",")
        if item.strip()
    )
    try:
        IndexConfig(enabled_modalities=modalities)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    return modalities


def _active_config() -> tuple[IndexConfig, dict]:
    status = require_ready_index()
    try:
        return local_config_from_status(status), status
    except IndexSchemaError as exc:
        raise IndexNotReadyError(str(exc)) from exc


def _require_modality(config: IndexConfig, modality: str) -> None:
    if modality not in config.enabled_modalities:
        raise IndexNotReadyError(
            f"The {modality} modality is not present in this index."
        )


@app.command()
def videoindex(
    path: str,
    modalities: Annotated[
        str,
        typer.Option(
            "--modalities",
            "-m",
            help="Comma-separated dialogue, scene, and actor modalities.",
        ),
    ] = "dialogue,scene,actor",
    frame_stride: Annotated[
        int,
        typer.Option(
            "--frame-stride",
            min=1,
            help=(
                "Materialize every Nth frame for scene and actor modalities."
            ),
        ),
    ] = 1,
):
    """Index one local video, replacing the previous local index."""

    config = IndexConfig.local(
        enabled_modalities=_modalities(modalities),
        frame_stride=frame_stride,
    )
    last_stage = None
    last_percent = None

    def progress(event):
        nonlocal last_percent, last_stage
        stage = event["stage"]
        current, total = event.get("current"), event.get("total")
        percent = (
            int(current * 100 / total)
            if current is not None and total
            else None
        )
        if stage != last_stage:
            print(f"[cyan]{event['message']}[/cyan]")
            last_stage = stage
            last_percent = percent
        elif percent is not None and (
            last_percent is None or percent >= last_percent + 10
        ):
            print(f"[cyan]{event['message']} {percent}%[/cyan]")
            last_percent = percent

    summary = index_video(path, progress_callback=progress, config=config)
    print("[bold green]Video indexing completed successfully.[/bold green]")
    return summary


@app.command()
def doctor(
    modalities: Annotated[
        str,
        typer.Option(
            "--modalities",
            "-m",
            help="Only validate dependencies for these modalities.",
        ),
    ] = "dialogue,scene,actor",
):
    """Validate selected indexing dependencies without downloading models."""

    selected = _modalities(modalities)
    failures = dict(
        dependency_failures(
            selected,
            needs_transcription="dialogue" in selected,
        )
    )
    checked_labels = []
    for modality in selected:
        for dependency in INDEXING_DEPENDENCIES[modality]:
            if dependency.label not in checked_labels:
                checked_labels.append(dependency.label)
    if "dialogue" in selected:
        for dependency in INDEXING_DEPENDENCIES["transcription"]:
            if dependency.label not in checked_labels:
                checked_labels.append(dependency.label)

    for label in checked_labels:
        if label in failures:
            print(f"[bold red]FAILED[/bold red] {label}: {failures[label]}")
        else:
            print(f"[green]OK[/green] {label}")

    if "dialogue" in selected:
        try:
            resolved_ffmpeg = ffmpeg_binary()
            print(f"[green]OK[/green] FFmpeg: {resolved_ffmpeg}")
        except Exception as exc:
            failures["FFmpeg"] = f"{type(exc).__name__}: {exc}"
            print(f"[bold red]FAILED[/bold red] FFmpeg: {failures['FFmpeg']}")

    if failures:
        raise typer.Exit(1)
    print("[bold green]Selected VidXP dependencies are available.[/bold green]")


@app.command()
def prepare(
    modalities: Annotated[
        str,
        typer.Option(
            "--modalities",
            "-m",
            help="Only prepare models for these modalities.",
        ),
    ] = "dialogue,scene",
    language: Annotated[
        str | None,
        typer.Option(
            "--language",
            "-l",
            help="Also cache the WhisperX alignment model for this language.",
        ),
    ] = None,
):
    """Download and cache selected runtime models before indexing."""

    selected = _modalities(modalities)
    config = IndexConfig.local(enabled_modalities=selected)
    try:
        failures = dependency_failures(
            selected,
            needs_transcription="dialogue" in selected,
        )
        if failures:
            details = "; ".join(
                f"{label}: {error}" for label, error in failures
            )
            raise RuntimeError(details)
        if "dialogue" in selected:
            print(f"[cyan]Preparing dialogue model: {config.sentence_model}[/cyan]")
            get_embedder(config.sentence_model, config.device)
            print(
                f"[cyan]Preparing transcription model: "
                f"WhisperX {config.whisper_model}[/cyan]"
            )
            get_whisper_model(config.whisper_model, config.device)
            if language:
                print(f"[cyan]Preparing the {language} alignment model.[/cyan]")
                get_alignment_model(language, config.device)
        if "scene" in selected:
            print(f"[cyan]Preparing scene model: CLIP {config.clip_model}[/cyan]")
            get_clip_model(config.clip_model, config.device)
    except Exception as exc:
        print(
            f"[bold red]Model preparation failed: "
            f"{type(exc).__name__}: {exc}[/bold red]"
        )
        raise typer.Exit(1) from exc
    print("[bold green]Selected VidXP runtime models are prepared.[/bold green]")


@app.command()
def dialogue(query: str):
    config, _ = _active_config()
    _require_modality(config, "dialogue")
    print("[green]Searching dialogue...[/green]")
    result = search_dialogue(
        query,
        config=config,
        top_k=1,
        video_id=config.video_id,
    )
    if not result.hits:
        raise IndexNotReadyError(
            "The completed index contains no searchable dialogue phrases."
        )
    print("[green]Dialogue found !!![/green]")
    timestamp = result.hits[0].start
    print(f"[bold green]{timestamp:.3f} seconds[/bold green]")
    return timestamp


@app.command()
def scene(query: str):
    config, _ = _active_config()
    _require_modality(config, "scene")
    print("[green]Searching scene...[/green]")
    result = search_scene(
        query,
        config=config,
        top_k=1,
        video_id=config.video_id,
    )
    if not result.hits:
        raise IndexNotReadyError(
            "The completed index contains no searchable scene frames."
        )
    print("[green]Scene found...[/green]")
    timestamp = result.hits[0].start
    print(f"[bold green]{timestamp:.3f} seconds[/bold green]")
    return timestamp


@app.command()
def actor(cluster_id: str, input_path: str, output_path: str = "output.mp4"):
    config, _ = _active_config()
    _require_modality(config, "actor")
    try:
        render_actor_result(
            config,
            cluster_id,
            input_path,
            output_path,
        )
    except ActorClusterNotFoundError as exc:
        raise IndexNotReadyError(
            str(exc)
        ) from exc
    print(f"[green]Video saved as {output_path}[/green]")


def main():
    try:
        app()
    except (IndexNotReadyError, IndexingInProgressError) as exc:
        print(f"[bold red]{exc}[/bold red]")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()

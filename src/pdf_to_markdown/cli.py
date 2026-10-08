"""Typer application and console entry point."""

from importlib.metadata import version
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from pdf_to_markdown.contracts import ArgumentError, ConversionError
from pdf_to_markdown.conversion import convert_pdf
from pdf_to_markdown.settings import Settings, SettingsError, load_settings

console = Console()
app = typer.Typer(
    name="pdf-to-markdown",
    help=(
        "Convert one whole RPG PDF into Markdown and linked local images.\n\n"
        "English OCR runs locally when needed. Results include physical page "
        "references and a conversion report.\n\n"
        "Choose a converter in settings.yaml: docling, marker, pymupdf4llm, "
        "or mineru. Run show-settings to see the active selection."
    ),
    epilog=(
        "### Quick start\n\n"
        "```sh\n"
        'pdf-to-markdown convert "Dragon Keep.pdf" \\\n'
        "  -o out/dragon-keep\n"
        "pdf-to-markdown --settings marker.yaml \\\n"
        "  convert adventure.pdf -o out/marker\n"
        "```\n\n"
        "Place the global `--settings FILE` option **before** the command. "
        "Set `converter: marker` in that YAML file to select Marker. Missing or "
        "empty implicit settings use Docling; an explicit file must exist.\n\n"
        "For conversion details: `pdf-to-markdown convert --help`.\n\n"
        "**Exit codes:** 0 = completed (warnings allowed); 1 = processing "
        "failed; 2 = invalid arguments or settings."
    ),
    no_args_is_help=True,
    rich_markup_mode="markdown",
)


def show_version(value: bool) -> None:
    """Print the installed package version and exit."""
    if value:
        console.print(f"[bold]pdf-to-markdown[/bold] {version('pdf-to-markdown')}")
        raise typer.Exit()


@app.callback()
def cli(
    ctx: typer.Context,
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=show_version,
            is_eager=True,
            help="Show the installed version and exit.",
        ),
    ] = False,
    settings: Annotated[
        Path | None,
        typer.Option(
            "--settings",
            metavar="FILE",
            help=(
                "YAML settings file. Default: settings.yaml in the current "
                "directory. Place this option before the command."
            ),
        ),
    ] = None,
) -> None:
    """PDF to Markdown command-line tools."""
    # Defer validation until a command executes, so help remains available
    # when settings are missing, unreadable, or invalid.
    ctx.obj = settings


def command_settings(ctx: typer.Context) -> Settings:
    """Load global settings only for a command that needs them."""
    try:
        return load_settings(ctx.obj)
    except SettingsError as exc:
        Console(stderr=True).print(f"Settings error: {exc}", style="red", markup=False)
        raise typer.Exit(code=2) from exc


@app.command(
    "show-settings",
    epilog=(
        "### Examples\n\n"
        "```sh\n"
        "pdf-to-markdown show-settings\n"
        "pdf-to-markdown --settings marker.yaml show-settings\n"
        "```"
    ),
)
def show_settings(ctx: typer.Context) -> None:
    """Show the active converter from the validated settings.

    Reads settings.yaml in the current directory, or the global --settings FILE.
    A missing or empty implicit file uses Docling. Invalid settings or a missing
    explicitly requested file exit with code 2.
    """
    settings = command_settings(ctx)
    console.print(f"converter: {settings.converter.value}", markup=False)


@app.command(
    "convert",
    epilog=(
        "### Examples\n\n"
        "```sh\n"
        'pdf-to-markdown convert "Dragon Keep.pdf" \\\n'
        "  --output out/dragon-keep\n"
        "pdf-to-markdown --settings marker.yaml \\\n"
        "  convert adventure.pdf -o out/marker\n"
        "```\n\n"
        "Choose the converter through `settings.yaml` or a global `--settings FILE` "
        "placed before `convert`. Run `pdf-to-markdown show-settings` to check it.\n\n"
        "The terminal summary gives the saved report location. Review important "
        "rules, numbers, and tables against the PDF; completed processing "
        "does not certify extraction accuracy."
    ),
)
def convert(
    ctx: typer.Context,
    pdf: Annotated[
        Path,
        typer.Argument(
            metavar="PDF",
            help="Path to one readable, unencrypted PDF. Quote paths with spaces.",
        ),
    ],
    output: Annotated[
        Path,
        typer.Option(
            "--output",
            "-o",
            metavar="FOLDER",
            help="Folder for Markdown, linked images, and report. Created if needed.",
        ),
    ],
) -> None:
    """Convert the whole PDF with local English OCR when needed.

    Produces Markdown, linked image assets, physical page comments starting at 1,
    and a report. Filenames and table formatting follow the selected converter.

    First use downloads required models with visible progress and needs internet
    access. PDF extraction runs locally.

    A successful rerun replaces previous generated files and preserves unrelated
    files. A failed run preserves the previous result. Edited generated files or
    unrelated filename collisions stop replacement.
    """
    settings = command_settings(ctx)
    try:
        result = convert_pdf(pdf, output, settings.converter)
    except ArgumentError as exc:
        Console(stderr=True).print(f"Argument error: {exc}", style="red", markup=False)
        raise typer.Exit(code=2) from exc
    except ConversionError as exc:
        Console(stderr=True).print(
            f"Conversion failed: {exc}", style="red", markup=False
        )
        raise typer.Exit(code=1) from exc
    console.print(f"Output: {result['output']}", markup=False)
    console.print(
        f"Pages processed: {result['pages_processed']}  "
        f"Images saved: {result['images_saved']}  Warnings: {len(result['warnings'])}",
        markup=False,
    )
    for warning in result["warnings"][:5]:
        console.print(f"Warning: {warning['message']}", style="yellow", markup=False)
    console.print(f"Report: {result['report_path']}", markup=False)
    console.print("Processing completed; extracted content accuracy was not verified.")


def main() -> None:
    """Run the command-line application."""
    app()

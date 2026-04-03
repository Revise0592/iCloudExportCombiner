#!/usr/bin/env python3
"""
iCloud Export Combiner
Extracts iCloud Photos export .zip files and sorts contents into Photos and Videos folders.
Ignores .csv, .json, and other non-media files.
"""

import argparse
import re
import sys
import zipfile
from collections import Counter
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.table import Table
from rich import print as rprint

console = Console()

PHOTO_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".heic", ".heif",
    ".gif", ".tiff", ".tif", ".bmp", ".webp",
    ".raw", ".cr2", ".cr3", ".nef", ".arw",
    ".dng", ".orf", ".rw2", ".pef", ".srw",
}

VIDEO_EXTENSIONS = {
    ".mp4", ".mov", ".avi", ".mkv", ".m4v",
    ".wmv", ".flv", ".3gp", ".mts", ".m2ts",
    ".ts", ".vob", ".mpg", ".mpeg",
}

IGNORED_EXTENSIONS = {".csv", ".json", ".txt", ".xml", ".html"}


def find_zip_files(source_dir: Path) -> list[Path]:
    """Find and sort iCloud export zip files in the source directory."""
    pattern = re.compile(r"iCloud Photos Part (\d+) of \d+\.zip", re.IGNORECASE)
    zips = []

    for f in source_dir.iterdir():
        if f.suffix.lower() == ".zip":
            match = pattern.match(f.name)
            if match:
                part_num = int(match.group(1))
                zips.append((part_num, f))

    if not zips:
        # Fallback: grab all zips sorted naturally
        all_zips = sorted(source_dir.glob("*.zip"))
        if all_zips:
            console.print(
                "[yellow]Warning:[/yellow] No files matched the iCloud naming pattern. "
                "Processing all .zip files in alphabetical order."
            )
            return all_zips

    zips.sort(key=lambda x: x[0])
    return [f for _, f in zips]


def classify_file(filename: str) -> str | None:
    """Return 'photo', 'video', or None (to skip) based on file extension."""
    ext = Path(filename).suffix.lower()
    if ext in PHOTO_EXTENSIONS:
        return "photo"
    if ext in VIDEO_EXTENSIONS:
        return "video"
    return None  # skip


def extract_and_sort(
    zip_files: list[Path],
    output_dir: Path,
    dry_run: bool = False,
) -> dict:
    """Extract zip files and sort media into Photos/Videos directories."""
    photos_dir = output_dir / "Photos"
    videos_dir = output_dir / "Videos"

    if not dry_run:
        photos_dir.mkdir(parents=True, exist_ok=True)
        videos_dir.mkdir(parents=True, exist_ok=True)

    stats = {
        "photos": 0,
        "videos": 0,
        "skipped": 0,
        "skipped_extensions": Counter(),
        "duplicates": 0,
        "errors": 0,
        "zips_processed": 0,
    }

    progress = Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=console,
        expand=True,
    )

    with progress:
        zip_task = progress.add_task("Processing zip files", total=len(zip_files))

        for zip_path in zip_files:
            progress.update(zip_task, description=f"[bold blue]{zip_path.name}")

            try:
                with zipfile.ZipFile(zip_path, "r") as zf:
                    members = [m for m in zf.infolist() if not m.is_dir()]
                    file_task = progress.add_task(
                        f"  Extracting", total=len(members), visible=True
                    )

                    for member in members:
                        filename = Path(member.filename).name
                        progress.update(file_task, description=f"  [dim]{filename[:50]}")

                        kind = classify_file(filename)

                        if kind is None:
                            stats["skipped"] += 1
                            ext = Path(filename).suffix.lower() or "(no extension)"
                            stats["skipped_extensions"][ext] += 1
                            progress.advance(file_task)
                            continue

                        dest_dir = photos_dir if kind == "photo" else videos_dir
                        dest_path = dest_dir / filename

                        # Handle duplicates by appending a counter
                        if dest_path.exists():
                            stem = dest_path.stem
                            suffix = dest_path.suffix
                            counter = 1
                            while dest_path.exists():
                                dest_path = dest_dir / f"{stem}_{counter}{suffix}"
                                counter += 1
                            stats["duplicates"] += 1

                        if not dry_run:
                            try:
                                data = zf.read(member.filename)
                                dest_path.write_bytes(data)
                            except Exception as e:
                                console.print(
                                    f"[red]Error extracting {filename}:[/red] {e}"
                                )
                                stats["errors"] += 1
                                progress.advance(file_task)
                                continue

                        if kind == "photo":
                            stats["photos"] += 1
                        else:
                            stats["videos"] += 1

                        progress.advance(file_task)

                    progress.remove_task(file_task)

            except zipfile.BadZipFile:
                console.print(f"[red]Bad zip file:[/red] {zip_path.name}")
                stats["errors"] += 1
            except Exception as e:
                console.print(f"[red]Error processing {zip_path.name}:[/red] {e}")
                stats["errors"] += 1

            stats["zips_processed"] += 1
            progress.advance(zip_task)

    return stats


def print_summary(zip_files: list[Path], stats: dict, output_dir: Path, dry_run: bool):
    table = Table(title="Summary", show_header=False, box=None, padding=(0, 2))
    table.add_column(style="bold cyan", justify="right")
    table.add_column()

    table.add_row("Zip files processed:", str(stats["zips_processed"]))
    table.add_row("Photos extracted:", f"[green]{stats['photos']}[/green]")
    table.add_row("Videos extracted:", f"[green]{stats['videos']}[/green]")
    table.add_row("Files skipped (non-media):", str(stats["skipped"]))
    table.add_row("Duplicate renames:", str(stats["duplicates"]))
    if stats["errors"]:
        table.add_row("Errors:", f"[red]{stats['errors']}[/red]")

    if not dry_run:
        table.add_row("Output — Photos:", str(output_dir / "Photos"))
        table.add_row("Output — Videos:", str(output_dir / "Videos"))

    prefix = "[yellow]DRY RUN — [/yellow]" if dry_run else ""
    console.print(Panel(table, title=f"{prefix}Extraction Complete", border_style="green"))

    if stats["skipped_extensions"]:
        skip_table = Table(
            title="Skipped file types",
            show_header=True,
            header_style="bold dim",
            box=None,
            padding=(0, 2),
        )
        skip_table.add_column("Extension", style="dim")
        skip_table.add_column("Count", justify="right", style="dim")
        for ext, count in stats["skipped_extensions"].most_common():
            skip_table.add_row(ext, str(count))
        console.print(skip_table)


def main():
    parser = argparse.ArgumentParser(
        description="Extract and sort iCloud Photos export zip files into Photos and Videos."
    )
    parser.add_argument(
        "source",
        nargs="?",
        default=".",
        help="Directory containing the iCloud export .zip files (default: current directory)",
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="Output directory for sorted files (default: same as source)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scan and report without extracting any files",
    )
    args = parser.parse_args()

    source_dir = Path(args.source).resolve()
    output_dir = Path(args.output).resolve() if args.output else source_dir

    if not source_dir.is_dir():
        console.print(f"[red]Error:[/red] Source directory not found: {source_dir}")
        sys.exit(1)

    console.print(
        Panel.fit(
            "[bold]iCloud Export Combiner[/bold]\n"
            f"Source: [cyan]{source_dir}[/cyan]\n"
            f"Output: [cyan]{output_dir}[/cyan]"
            + ("[yellow]  (DRY RUN)[/yellow]" if args.dry_run else ""),
            border_style="blue",
        )
    )

    zip_files = find_zip_files(source_dir)

    if not zip_files:
        console.print("[red]No iCloud export zip files found in the source directory.[/red]")
        sys.exit(1)

    console.print(f"Found [bold]{len(zip_files)}[/bold] zip file(s) to process.\n")

    stats = extract_and_sort(zip_files, output_dir, dry_run=args.dry_run)
    print_summary(zip_files, stats, output_dir, dry_run=args.dry_run)


if __name__ == "__main__":
    main()

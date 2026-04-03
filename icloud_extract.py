#!/usr/bin/env python3
"""
iCloud Export Combiner
Extracts iCloud Photos export .zip files and sorts contents into Photos and Videos folders.
Ignores .csv, .json, and other non-media files.
No third-party dependencies — stdlib only.
"""

import argparse
import re
import sys
import zipfile
from collections import Counter
from pathlib import Path

# ---------------------------------------------------------------------------
# ANSI helpers
# ---------------------------------------------------------------------------

RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RED    = "\033[31m"
GREEN  = "\033[32m"
YELLOW = "\033[33m"
CYAN   = "\033[36m"


def c(text, *codes):
    return "".join(codes) + str(text) + RESET


def print_header(source_dir: Path, output_dir: Path, dry_run: bool):
    dry = f"  {c('(DRY RUN)', YELLOW, BOLD)}" if dry_run else ""
    print(f"\n{c('iCloud Export Combiner', BOLD, CYAN)}{dry}")
    print(f"  Source : {c(source_dir, CYAN)}")
    print(f"  Output : {c(output_dir, CYAN)}")
    print()


# ---------------------------------------------------------------------------
# Media classification
# ---------------------------------------------------------------------------

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


def classify_file(filename: str) -> str | None:
    """Return 'photo', 'video', or None (skip) based on extension."""
    ext = Path(filename).suffix.lower()
    if ext in PHOTO_EXTENSIONS:
        return "photo"
    if ext in VIDEO_EXTENSIONS:
        return "video"
    return None


# ---------------------------------------------------------------------------
# Zip discovery
# ---------------------------------------------------------------------------

def find_zip_files(source_dir: Path) -> list[Path]:
    pattern = re.compile(r"iCloud Photos Part (\d+) of \d+\.zip", re.IGNORECASE)
    zips = []

    for f in source_dir.iterdir():
        if f.suffix.lower() == ".zip":
            match = pattern.match(f.name)
            if match:
                zips.append((int(match.group(1)), f))

    if not zips:
        all_zips = sorted(source_dir.glob("*.zip"))
        if all_zips:
            print(
                c("Warning:", YELLOW, BOLD)
                + " No files matched the iCloud naming pattern. "
                "Processing all .zip files alphabetically."
            )
            return all_zips
        return []

    zips.sort(key=lambda x: x[0])
    return [f for _, f in zips]


# ---------------------------------------------------------------------------
# Extraction + sorting
# ---------------------------------------------------------------------------

def extract_and_sort(zip_files: list[Path], output_dir: Path, dry_run: bool) -> dict:
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

    total_zips = len(zip_files)
    pad = len(str(total_zips))

    for idx, zip_path in enumerate(zip_files, 1):
        z_photos = z_videos = z_skipped = z_errors = 0

        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                for member in zf.infolist():
                    if member.is_dir():
                        continue
                    filename = Path(member.filename).name
                    kind = classify_file(filename)

                    if kind is None:
                        z_skipped += 1
                        ext = Path(filename).suffix.lower() or "(no extension)"
                        stats["skipped_extensions"][ext] += 1
                        continue

                    dest_dir = photos_dir if kind == "photo" else videos_dir
                    dest_path = dest_dir / filename

                    if dest_path.exists():
                        stem, suffix = dest_path.stem, dest_path.suffix
                        counter = 1
                        while dest_path.exists():
                            dest_path = dest_dir / f"{stem}_{counter}{suffix}"
                            counter += 1
                        stats["duplicates"] += 1

                    if not dry_run:
                        try:
                            dest_path.write_bytes(zf.read(member.filename))
                        except Exception as e:
                            print(f"  {c('Error', RED, BOLD)} extracting {filename}: {e}")
                            z_errors += 1
                            continue

                    if kind == "photo":
                        z_photos += 1
                    else:
                        z_videos += 1

        except zipfile.BadZipFile:
            print(f"[{idx:{pad}}/{total_zips}] {zip_path.name}  {c('bad zip — skipped', RED)}")
            stats["errors"] += 1
            stats["zips_processed"] += 1
            continue
        except Exception as e:
            print(f"[{idx:{pad}}/{total_zips}] {zip_path.name}  {c(e, RED)}")
            stats["errors"] += 1
            stats["zips_processed"] += 1
            continue

        stats["photos"] += z_photos
        stats["videos"] += z_videos
        stats["skipped"] += z_skipped
        stats["errors"] += z_errors
        stats["zips_processed"] += 1

        parts = [c(f"{z_photos} photos", GREEN), c(f"{z_videos} videos", CYAN)]
        if z_skipped:
            parts.append(c(f"{z_skipped} skipped", DIM))
        if z_errors:
            parts.append(c(f"{z_errors} errors", RED))
        print(f"[{idx:{pad}}/{total_zips}] {zip_path.name}  {', '.join(parts)}")

    return stats


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def print_summary(stats: dict, output_dir: Path, dry_run: bool):
    prefix = c("DRY RUN  ", YELLOW, BOLD) if dry_run else ""
    print(f"\n{prefix}{c('Results', BOLD)}")
    print(f"  {'Zip files processed':<28} {stats['zips_processed']}")
    print(f"  {'Photos extracted':<28} {c(stats['photos'], GREEN, BOLD)}")
    print(f"  {'Videos extracted':<28} {c(stats['videos'], GREEN, BOLD)}")
    print(f"  {'Files skipped (non-media)':<28} {stats['skipped']}")
    print(f"  {'Duplicate renames':<28} {stats['duplicates']}")
    if stats["errors"]:
        print(f"  {'Errors':<28} {c(stats['errors'], RED, BOLD)}")
    if not dry_run:
        print(f"  {'Output — Photos':<28} {c(output_dir / 'Photos', CYAN)}")
        print(f"  {'Output — Videos':<28} {c(output_dir / 'Videos', CYAN)}")

    if stats["skipped_extensions"]:
        print(f"\n{c('Skipped file types', BOLD)}")
        for ext, count in stats["skipped_extensions"].most_common():
            print(f"  {ext:<20} {c(count, DIM)}")

    print()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

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
        print(f"{c('Error:', RED, BOLD)} Source directory not found: {source_dir}")
        sys.exit(1)

    print_header(source_dir, output_dir, args.dry_run)

    zip_files = find_zip_files(source_dir)
    if not zip_files:
        print(f"{c('Error:', RED, BOLD)} No iCloud export zip files found in the source directory.")
        sys.exit(1)

    print(f"Found {c(len(zip_files), BOLD)} zip file(s) to process.\n")

    stats = extract_and_sort(zip_files, output_dir, dry_run=args.dry_run)
    print_summary(stats, output_dir, dry_run=args.dry_run)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Helper utility to collect rich metadata from PDFs, images, and videos into a
single CSV using ExifTool.

This script wraps the ExifTool command-line options used most often when
surveying a large evidence folder:

* Requests comprehensive output (`RequestAll=3`) and enables large-file support.
* Recursively traverses the provided root folder.
* Filters to a configurable list of extensions.
* Writes results directly to a CSV that is easy to open in Excel.

Example:
    python tools/metadata_dump.py /path/to/evidence --output metadata.csv
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Iterable, List, Sequence

DEFAULT_EXTENSIONS = [
    "pdf",
    "jpg",
    "jpeg",
    "png",
    "tif",
    "tiff",
    "heic",
    "mp4",
    "mov",
    "avi",
    "mkv",
]

DEFAULT_OUTPUT = "metadata_master.csv"


def normalize_extensions(extensions: Iterable[str]) -> List[str]:
    """Normalize extensions to lowercase strings without leading dots."""
    normalized = []
    for ext in extensions:
        ext = ext.strip().lower()
        if ext.startswith("."):
            ext = ext[1:]
        if not ext:
            continue
        normalized.append(ext)
    if not normalized:
        raise ValueError("At least one file extension must be provided.")
    return normalized


def build_exiftool_command(
    root_dir: Path,
    extensions: Iterable[str],
    *,
    request_all: int = 3,
    largefile_support: bool = True,
    recursive: bool = True,
    exiftool_cmd: str = "exiftool",
) -> List[str]:
    """Construct the ExifTool command to run.

    Args:
        root_dir: Top-level folder containing evidence files.
        extensions: File extensions to include.
        request_all: Value for the ExifTool RequestAll API option.
        largefile_support: Whether to enable large file support for videos.
        recursive: Whether to scan subdirectories.
        exiftool_cmd: ExifTool executable to invoke.

    Returns:
        A list representing the ExifTool command and its arguments.
    """

    normalized_exts = normalize_extensions(extensions)

    cmd = [exiftool_cmd, "-api", f"RequestAll={request_all}"]
    if largefile_support:
        cmd.extend(["-api", "largefilesupport=1"])
    cmd.extend(["-G1", "-csv"])
    if recursive:
        cmd.append("-r")

    for ext in normalized_exts:
        cmd.extend(["-ext", ext])

    cmd.append(str(root_dir))
    return cmd


def run_exiftool_metadata_dump(
    root_dir: Path,
    output_csv: Path,
    *,
    extensions: Iterable[str] = DEFAULT_EXTENSIONS,
    request_all: int = 3,
    largefile_support: bool = True,
    recursive: bool = True,
    exiftool_cmd: str = "exiftool",
    force: bool = False,
) -> None:
    """Run ExifTool and write metadata to the provided CSV path."""

    if not root_dir.is_dir():
        raise FileNotFoundError(f"Root directory does not exist: {root_dir}")

    resolved_output = output_csv.resolve()
    resolved_output.parent.mkdir(parents=True, exist_ok=True)

    if shutil.which(exiftool_cmd) is None:
        raise FileNotFoundError(
            f"ExifTool executable '{exiftool_cmd}' could not be found on PATH."
        )

    if resolved_output.exists():
        if not force:
            raise FileExistsError(
                f"Output file already exists: {resolved_output}. "
                "Use --force to overwrite."
            )
        resolved_output.unlink()

    cmd = build_exiftool_command(
        root_dir,
        extensions,
        request_all=request_all,
        largefile_support=largefile_support,
        recursive=recursive,
        exiftool_cmd=exiftool_cmd,
    )

    print("Running ExifTool... this can take a while on large trees.")
    print("Command:", " ".join(cmd))

    with resolved_output.open("w", encoding="utf-8", newline="") as handle:
        subprocess.run(cmd, check=True, stdout=handle)

    print(f"Done. Metadata written to: {resolved_output}")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Recursively export metadata for PDFs, images, and videos to a CSV "
            "via ExifTool."
        )
    )
    parser.add_argument(
        "root_dir",
        type=Path,
        help="Top-level directory that contains the evidence files.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path(DEFAULT_OUTPUT),
        help=f"Path to write the CSV file (default: {DEFAULT_OUTPUT}).",
    )
    parser.add_argument(
        "-e",
        "--ext",
        dest="extensions",
        nargs="+",
        default=DEFAULT_EXTENSIONS,
        help="File extensions to include (defaults cover common media types).",
    )
    parser.add_argument(
        "--request-all",
        type=int,
        default=3,
        help="RequestAll API level passed to ExifTool (default: 3).",
    )
    parser.add_argument(
        "--no-largefile-support",
        action="store_true",
        help="Disable ExifTool's large file support option.",
    )
    parser.add_argument(
        "--no-recursive",
        action="store_true",
        help="Do not recurse into subfolders.",
    )
    parser.add_argument(
        "--exiftool",
        dest="exiftool_cmd",
        default="exiftool",
        help="ExifTool executable to invoke (default: 'exiftool').",
    )
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Overwrite the output file if it already exists.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        run_exiftool_metadata_dump(
            root_dir=args.root_dir,
            output_csv=args.output,
            extensions=args.extensions,
            request_all=args.request_all,
            largefile_support=not args.no_largefile_support,
            recursive=not args.no_recursive,
            exiftool_cmd=args.exiftool_cmd,
            force=args.force,
        )
    except Exception as exc:  # noqa: BLE001 - surface clear CLI error message
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Utility helpers to explore ExifTool JSON output with pandas.

This script is intentionally lightweight so it can be used as a quick
reference for analyzing ExifTool JSON dumps.  It flattens the JSON using
``pandas.json_normalize`` so nested structures become dot-separated column
names that are easy to filter and summarize.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List

import pandas as pd


def _load_json_documents(json_path: Path) -> List[dict]:
    """Load one or more JSON documents from ``json_path``.

    ExifTool's ``-j`` output is typically a list of dictionaries.  If the file
    contains a single dictionary, it is wrapped into a list so downstream code
    always receives an iterable collection.
    """

    with json_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        return [payload]

    raise ValueError(
        f"Expected a dictionary or list of dictionaries in {json_path}, "
        f"got {type(payload).__name__} instead."
    )


def load_metadata_frame(json_path: Path) -> pd.DataFrame:
    """Return a flattened DataFrame containing metadata from ``json_path``.

    Nested objects are flattened using dot-separated names to make grouping and
    filtering simpler in pandas.  Columns are sorted alphabetically for easier
    scanning and stable summaries.
    """

    records = _load_json_documents(json_path)
    frame = pd.json_normalize(records, sep=".")
    return frame.reindex(sorted(frame.columns), axis=1)


def summarize_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """Generate a summary with non-null counts and unique value counts."""

    summary_rows = []
    for column in frame.columns:
        series = frame[column]
        summary_rows.append(
            {
                "Tag": column,
                "NonNullCount": int(series.notna().sum()),
                "UniqueValues": int(series.nunique(dropna=True)),
            }
        )
    return pd.DataFrame(summary_rows).sort_values("Tag").reset_index(drop=True)


def compare_summaries(new: pd.DataFrame, existing: pd.DataFrame) -> pd.DataFrame:
    """Return rows where summary statistics differ between two DataFrames."""

    merged = existing.merge(new, on="Tag", how="outer", suffixes=("_old", "_new"))
    mismatched = merged[
        (merged["NonNullCount_old"] != merged["NonNullCount_new"])
        | (merged["UniqueValues_old"] != merged["UniqueValues_new"])
    ]
    return mismatched.sort_values("Tag").reset_index(drop=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("json_path", type=Path, help="Path to ExifTool JSON output")
    parser.add_argument(
        "--write-summary",
        dest="summary_path",
        type=Path,
        help="Optional path to write the generated column summary as CSV",
    )
    parser.add_argument(
        "--compare-summary",
        dest="existing_summary",
        type=Path,
        help="Optional CSV created by this script to compare against",
    )
    parser.add_argument(
        "--head",
        type=int,
        default=5,
        help="Number of rows from the flattened metadata to display for quick inspection",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    frame = load_metadata_frame(args.json_path)
    summary = summarize_columns(frame)

    print(f"Loaded {len(frame)} metadata record(s) with {len(frame.columns)} tag columns.")
    if args.head:
        print("\nSample rows (flattened):")
        print(frame.head(args.head).to_string(index=False))

    print("\nColumn summary:")
    print(summary.to_string(index=False))

    if args.summary_path:
        summary.to_csv(args.summary_path, index=False)
        print(f"\nWrote summary CSV to {args.summary_path}")

    if args.existing_summary and args.existing_summary.exists():
        existing = pd.read_csv(args.existing_summary)
        differences = compare_summaries(summary, existing)
        if differences.empty:
            print("\nNo differences detected when compared to existing summary.")
        else:
            print("\nDifferences compared to existing summary:")
            print(differences.to_string(index=False))


if __name__ == "__main__":
    main()

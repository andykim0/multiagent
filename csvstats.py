#!/usr/bin/env python3
"""Print per-column statistics for a CSV file."""

import argparse
import csv
import json
import math
import statistics
import sys


ERROR_PREFIX = "csvstats: error: "
RAGGED_WARNING = (
    "csvstats: warning: ragged rows found; short rows padded, "
    "extra fields ignored"
)


class CsvstatsArgumentParser(argparse.ArgumentParser):
    """Argument parser with the required one-line usage errors."""

    def error(self, message):
        self.exit(1, f"{ERROR_PREFIX}{message}\n")


def build_parser():
    """Create the command-line parser."""
    parser = CsvstatsArgumentParser(
        prog="csvstats",
        description="Print per-column statistics for a CSV file.",
        epilog="exit codes: 0 success, 1 data error, 2 file error",
    )
    parser.add_argument("file", metavar="FILE", help="path to the CSV file")
    parser.add_argument(
        "--delimiter",
        metavar="CHAR",
        default=",",
        help='field delimiter (default: ",")',
    )
    parser.add_argument(
        "--no-header",
        action="store_true",
        help="treat the first row as data and name columns col1..colN",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="output_json",
        help="print JSON instead of the formatted table",
    )
    return parser


def _delimiter_for_message(value):
    """Keep delimiter errors on one line when the value is CR or LF."""
    return value.replace("\r", r"\r").replace("\n", r"\n")


def validate_delimiter(parser, delimiter):
    """Reject delimiters that csv.reader cannot safely accept."""
    if len(delimiter) != 1 or delimiter in {'"', "\r", "\n"}:
        shown = _delimiter_for_message(delimiter)
        parser.error(
            "--delimiter must be a single character other than "
            f"'\"', CR or LF (got '{shown}')"
        )


def read_rows(path, delimiter, no_header):
    """Read and normalize CSV rows, returning names, data, and ragged state."""
    nonblank_rows = []
    with open(path, "r", encoding="utf-8-sig", newline="") as handle:
        for raw_row in csv.reader(handle, delimiter=delimiter):
            if not raw_row:
                continue
            nonblank_rows.append([field.strip() for field in raw_row])

    if not nonblank_rows:
        return None, [], False

    if no_header:
        first_row = nonblank_rows[0]
        names = [f"col{index}" for index in range(1, len(first_row) + 1)]
        candidate_rows = nonblank_rows
    else:
        names = nonblank_rows[0]
        candidate_rows = nonblank_rows[1:]

    width = len(names)
    rows = []
    ragged = False
    for row in candidate_rows:
        if len(row) != width:
            ragged = True
        normalized = row[:width]
        if len(normalized) < width:
            normalized.extend([""] * (width - len(normalized)))
        rows.append(normalized)

    return names, rows, ragged


def analyze_column(name, values):
    """Infer one column's type and calculate its statistics."""
    present = [value for value in values if value != ""]
    count = len(present)
    missing = len(values) - count

    numbers = []
    numeric = count > 0
    if numeric:
        for value in present:
            try:
                number = float(value)
            except (ValueError, OverflowError):
                numeric = False
                break
            if not math.isfinite(number):
                numeric = False
                break
            numbers.append(number)

    result = {
        "name": name,
        "type": "numeric" if numeric else "text",
        "count": count,
        "missing": missing,
    }

    if numeric:
        result["min"] = float(min(numbers)) if numbers else None
        result["max"] = float(max(numbers)) if numbers else None
        result["mean"] = float(statistics.mean(numbers)) if numbers else None
        result["median"] = float(statistics.median(numbers)) if numbers else None
        result["stdev"] = (
            float(statistics.stdev(numbers)) if len(numbers) >= 2 else None
        )
    else:
        frequencies = {}
        for value in present:
            frequencies[value] = frequencies.get(value, 0) + 1
        result["unique"] = len(frequencies)
        result["top"] = (
            max(frequencies, key=frequencies.get) if frequencies else None
        )

    return result


def analyze(names, rows):
    """Analyze all columns in positional file order."""
    return [
        analyze_column(name, [row[index] for row in rows])
        for index, name in enumerate(names)
    ]


def fmt_num(value):
    """Format a numeric statistic for table output."""
    if math.isnan(value):
        return "nan"
    if math.isinf(value):
        return "inf" if value > 0 else "-inf"
    absolute = abs(value)
    if value != 0 and (absolute >= 1e12 or absolute < 1e-4):
        return "%.4e" % value
    rendered = ("%.4f" % value).rstrip("0").rstrip(".")
    return "0" if rendered == "-0" else rendered


def display_text(value):
    """Sanitize and truncate data for table display only."""
    safe = "".join(
        " " if ord(character) < 0x20 or ord(character) == 0x7F else character
        for character in value
    )
    if len(safe) > 20:
        return safe[:17] + "..."
    return safe


def render_section(heading, headers, alignments, rows):
    """Render one content-sized table section."""
    widths = []
    for index, header in enumerate(headers):
        widths.append(
            max([len(header)] + [len(row[index]) for row in rows])
        )

    def render_row(cells):
        rendered = []
        for cell, width, alignment in zip(cells, widths, alignments):
            if alignment == "right":
                rendered.append(cell.rjust(width))
            else:
                rendered.append(cell.ljust(width))
        return "  ".join(rendered).rstrip()

    lines = [
        heading,
        render_row(headers),
        "  ".join("-" * width for width in widths),
    ]
    lines.extend(render_row(row) for row in rows)
    return "\n".join(lines)


def render_table(path, row_count, columns):
    """Render the complete human-readable report."""
    row_word = "row" if row_count == 1 else "rows"
    column_word = "column" if len(columns) == 1 else "columns"
    blocks = [
        f"{path}: {row_count} {row_word}, {len(columns)} {column_word}"
    ]

    numeric_rows = []
    text_rows = []
    for index, column in enumerate(columns, start=1):
        name = display_text(column["name"])
        if column["type"] == "numeric":
            numeric_rows.append(
                [
                    str(index),
                    name,
                    str(column["count"]),
                    str(column["missing"]),
                    fmt_num(column["min"]) if column["min"] is not None else "N/A",
                    fmt_num(column["max"]) if column["max"] is not None else "N/A",
                    (
                        fmt_num(column["mean"])
                        if column["mean"] is not None
                        else "N/A"
                    ),
                    (
                        fmt_num(column["median"])
                        if column["median"] is not None
                        else "N/A"
                    ),
                    (
                        fmt_num(column["stdev"])
                        if column["stdev"] is not None
                        else "N/A"
                    ),
                ]
            )
        else:
            text_rows.append(
                [
                    str(index),
                    name,
                    str(column["count"]),
                    str(column["missing"]),
                    str(column["unique"]),
                    (
                        display_text(column["top"])
                        if column["top"] is not None
                        else "N/A"
                    ),
                ]
            )

    if numeric_rows:
        blocks.append(
            render_section(
                "Numeric columns:",
                ["#", "column", "count", "missing", "min", "max", "mean", "median", "stdev"],
                ["right", "left", "right", "right", "right", "right", "right", "right", "right"],
                numeric_rows,
            )
        )
    if text_rows:
        blocks.append(
            render_section(
                "Text columns:",
                ["#", "column", "count", "missing", "unique", "top"],
                ["right", "left", "right", "right", "right", "left"],
                text_rows,
            )
        )

    return "\n\n".join(blocks) + "\n"


def render_json(path, row_count, ragged, columns):
    """Render the machine-readable report."""
    payload = {
        "file": path,
        "rows": row_count,
        "ragged": ragged,
        "columns": columns,
    }
    return json.dumps(payload, indent=2, allow_nan=False) + "\n"


def _write_error(message):
    sys.stderr.write(f"{ERROR_PREFIX}{message}\n")


def main(argv):
    """Run csvstats and return its process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    validate_delimiter(parser, args.delimiter)

    try:
        names, rows, ragged = read_rows(
            args.file, args.delimiter, args.no_header
        )
    except FileNotFoundError:
        _write_error(f"no such file: {args.file}")
        return 2
    except PermissionError:
        _write_error(f"permission denied: {args.file}")
        return 2
    except IsADirectoryError:
        _write_error(f"is a directory: {args.file}")
        return 2
    except UnicodeDecodeError:
        _write_error(f"cannot decode as utf-8: {args.file}")
        return 2
    except csv.Error:
        _write_error(f"cannot parse as CSV: {args.file}")
        return 1
    except OSError:
        _write_error(f"cannot read file: {args.file}")
        return 2

    if names is None or (
        not args.no_header and not rows and all(name == "" for name in names)
    ):
        _write_error(f"no columns found: {args.file}")
        return 1

    columns = analyze(names, rows)
    if ragged:
        sys.stderr.write(RAGGED_WARNING + "\n")

    if args.output_json:
        sys.stdout.write(render_json(args.file, len(rows), ragged, columns))
    else:
        sys.stdout.write(render_table(args.file, len(rows), columns))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

#!/usr/bin/env python3
"""Convert GZoltar fault localization reports to a coverage matrix CSV."""
from __future__ import annotations

import argparse
import csv
from pathlib import Path


def read_methods(spectra_path: Path) -> list[str]:
    methods: list[str] = []
    with spectra_path.open(encoding="utf-8") as spectra_file:
        reader = csv.reader(spectra_file)
        next(reader, None)  # header ("name")
        for row in reader:
            if not row:
                continue
            method_name = ",".join(cell.strip() for cell in row if cell)
            methods.append(method_name)
    return methods


def read_tests(tests_path: Path) -> list[str]:
    tests: list[str] = []
    with tests_path.open(encoding="utf-8") as tests_file:
        reader = csv.reader(tests_file)
        next(reader, None)  # header
        for row in reader:
            if not row:
                continue
            tests.append(row[0])
    return tests


def read_matrix(matrix_path: Path) -> list[list[int]]:
    rows: list[list[int]] = []
    current: list[int] = []
    with matrix_path.open(encoding="utf-8") as matrix_file:
        for raw_line in matrix_file:
            line = raw_line.strip()
            if not line:
                continue

            continuation = False
            if line.endswith("\\"):
                continuation = True
                line = line[:-1]
            elif line.endswith("+"):
                line = line[:-1]

            tokens = [token for token in line.split() if token and token not in {'-', '+'}]
            try:
                current.extend(int(token) for token in tokens)
            except ValueError as exc:
                raise ValueError(f"Unexpected token in matrix.txt: {tokens}") from exc

            if not continuation:
                if current:
                    rows.append(current)
                    current = []
        if current:
            rows.append(current)
    return rows


def write_csv(output_path: Path, tests: list[str], methods: list[str], matrix: list[list[int]]) -> None:
    if len(matrix) != len(tests):
        raise ValueError(f"Matrix row count ({len(matrix)}) != tests count ({len(tests)})")
    if matrix and len(matrix[0]) != len(methods):
        raise ValueError(f"Matrix column count ({len(matrix[0])}) != methods count ({len(methods)})")

    with output_path.open("w", newline="", encoding="utf-8") as out_file:
        writer = csv.writer(out_file)
        writer.writerow(["test"] + methods)
        for test_name, row in zip(tests, matrix):
            writer.writerow([test_name] + row)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spectra", type=Path, help="Path to spectra.csv from GZoltar report")
    parser.add_argument("tests", type=Path, help="Path to tests.csv from GZoltar report")
    parser.add_argument("matrix_txt", type=Path, help="Path to matrix.txt from GZoltar report")
    parser.add_argument("output", type=Path, help="Destination CSV path")
    args = parser.parse_args()

    methods = read_methods(args.spectra)
    tests = read_tests(args.tests)
    matrix = read_matrix(args.matrix_txt)
    write_csv(args.output, tests, methods, matrix)


if __name__ == "__main__":
    main()

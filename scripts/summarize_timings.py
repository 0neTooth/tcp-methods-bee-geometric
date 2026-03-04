#!/usr/bin/env python3
"""Агрегирует timings.csv и добавляет среднее время по каждому режиму."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from statistics import mean


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Сводка средних таймингов по алгоритмам")
    parser.add_argument("--input", default="docs/lom_reports/timings.csv", help="Исходный CSV с таймингами")
    parser.add_argument("--output", help="Куда писать результат (по умолчанию перезаписывает input)")
    return parser.parse_args()


def read_rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        return list(reader)


def write_rows(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output) if args.output else input_path

    if not input_path.is_file():
        raise SystemExit(f"Input timings file not found: {input_path}")

    rows = read_rows(input_path)
    if not rows:
        raise SystemExit("No data in timings CSV")

    fieldnames = list(rows[0].keys())
    # убираем старые summary (project=ALL) и считаем только реальные строки
    data_rows = [r for r in rows if r.get("project") and r["project"] != "ALL"]

    by_mode: dict[str, list[float]] = {}
    for row in data_rows:
        mode = row.get("mode", "")
        try:
            duration = float(row.get("duration_sec", "0"))
        except ValueError:
            continue
        by_mode.setdefault(mode, []).append(duration)

    summary_rows: list[dict] = []
    for mode, values in by_mode.items():
        if not values:
            continue
        avg = mean(values)
        summary_rows.append({
            "project": "ALL",
            "bug": "ALL",
            "mode": mode,
            "clusters": "",
            "tests": "",
            "methods": "",
            "duration_sec": f"{avg:.4f}",
        })

    new_rows = data_rows + summary_rows
    write_rows(output_path, fieldnames, new_rows)
    print(f"[done] wrote summary to {output_path}")


if __name__ == "__main__":
    main()

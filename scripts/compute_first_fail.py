#!/usr/bin/env python3
"""Вычисляет first-fail (средняя доля тестов до первого падения)."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Dict, List


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="First-fail для заданного порядка тестов")
    parser.add_argument("--project", required=True)
    parser.add_argument("--bug", required=True)
    parser.add_argument("--order", required=True, help="Путь к CSV с порядком (rank,test,score)")
    parser.add_argument("--output", help="Путь для записи результата (CSV или TXT)")
    return parser.parse_args()


def load_order(order_path: Path, test_map: Dict[str, List[int]]) -> List[str]:
    ordered_tests: List[str] = []
    with order_path.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            test_id = row["test"].split("#", 1)[0]
            if test_id not in test_map:
                continue
            if test_id not in ordered_tests:
                ordered_tests.append(test_id)

    for test_id in test_map:
        if test_id not in ordered_tests:
            ordered_tests.append(test_id)
    return ordered_tests


def load_test_map(path: Path) -> Dict[str, List[int]]:
    mapping: Dict[str, List[int]] = {}
    with path.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            name = row["TestName"].strip()
            num = int(row["TestNo"])
            mapping.setdefault(name, []).append(num)
    return mapping


def load_killed_mutants(path: Path) -> List[int]:
    killed: List[int] = []
    with path.open(encoding="utf-8") as fh:
        reader = csv.reader(fh)
        next(reader, None)
        for row in reader:
            mutant_no = int(row[0])
            status = row[1].strip()
            if status in {"FAIL", "TIME", "EXC"}:
                killed.append(mutant_no)
    return killed


def load_cov_map(path: Path) -> Dict[int, List[int]]:
    mapping: Dict[int, List[int]] = {}
    with path.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            test_no = int(row["TestNo"])
            mutant_no = int(row["MutantNo"])
            mapping.setdefault(mutant_no, []).append(test_no)
    return mapping


def compute_first_fail(order: List[str], test_map: Dict[str, List[int]], killed: List[int], cov_map: Dict[int, List[int]]) -> float:
    test_order: Dict[int, int] = {}
    for index, test_name in enumerate(order, start=1):
        for test_no in test_map.get(test_name, []):
            test_order[test_no] = index

    n = len(order)
    if n == 0 or not killed:
        return 0.0

    total = 0
    for mutant in killed:
        tests = cov_map.get(mutant, [])
        positions = [test_order.get(t) for t in tests if t in test_order]
        if not positions:
            tf = n
        else:
            tf = min(positions)
        total += tf

    return total / (n * len(killed))


def main() -> None:
    args = parse_args()
    root = Path(__file__).resolve().parents[1]
    order_path = Path(args.order)

    test_map_path = root / "data" / "raw" / args.project / args.bug / "mutants" / "testMap.csv"
    kill_path = root / "data" / "raw" / args.project / args.bug / "mutants" / "kill.csv"
    cov_map_path = root / "data" / "raw" / args.project / args.bug / "mutants" / "covMap.csv"

    test_map = load_test_map(test_map_path)
    order = load_order(order_path, test_map)
    killed = load_killed_mutants(kill_path)
    cov_map = load_cov_map(cov_map_path)

    first_fail = compute_first_fail(order, test_map, killed, cov_map)
    message = f"FIRST_FAIL({args.project}-{args.bug}) = {first_fail * 100:.2f}"
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", encoding="utf-8") as fh:
            fh.write(message + "\n")
    print(message)


if __name__ == "__main__":
    main()

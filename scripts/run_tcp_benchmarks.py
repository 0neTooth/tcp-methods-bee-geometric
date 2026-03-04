#!/usr/bin/env python3
"""
Вычисление TCP-порядков (Total, Additional, Random) и APFD.
"""

from __future__ import annotations

import argparse
import csv
import random
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Set, Tuple
from time import perf_counter

from compute_apfd import compute_apfd, load_cov_map, load_killed_mutants, load_order, load_test_map

# подключаем общий код из lom-study
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lom-study"))

from tcp.data_loader import read_coverage_matrix  # type: ignore


class TCPBenchmarks:
    def __init__(self, project: str, bug: str):
        self.project = project
        self.bug = bug
        self.base_dir = ROOT / "data" / "raw" / project / bug
        self.coverage_matrix_path = self.base_dir / "coverage" / "matrix.csv"
        self.mutants_dir = self.base_dir / "mutants"
        self.results_dir = ROOT / "data" / "results" / "tcp" / project / bug
        self.results_dir.mkdir(parents=True, exist_ok=True)

        self.coverage = read_coverage_matrix(self.coverage_matrix_path)
        self.coverage_sets = self._build_coverage_sets()

    def _build_coverage_sets(self) -> Dict[str, Set[int]]:
        sets: Dict[str, Set[int]] = {}
        for test, row in zip(self.coverage.tests, self.coverage.hits):
            covered = {idx for idx, value in enumerate(row) if value}
            sets[test] = covered
        return sets

    def total_order(self) -> List[str]:
        scored = sorted(
            ((len(self.coverage_sets[test]), test) for test in self.coverage.tests),
            reverse=True,
        )
        return [test for _, test in scored]

    def additional_order(self) -> List[str]:
        remaining_methods = set().union(*self.coverage_sets.values())
        ordered: List[str] = []
        unused = set(self.coverage.tests)

        while remaining_methods and unused:
            best_test = None
            best_gain = -1
            for test in unused:
                gain = len(self.coverage_sets[test] & remaining_methods)
                if gain > best_gain:
                    best_gain = gain
                    best_test = test
            if best_test is None:
                break
            ordered.append(best_test)
            unused.remove(best_test)
            remaining_methods -= self.coverage_sets[best_test]

        ordered.extend(sorted(unused))
        return ordered

    def random_order(self, seed: int) -> List[str]:
        tests = list(self.coverage.tests)
        random.Random(seed).shuffle(tests)
        return tests

    def write_order(self, name: str, tests: Iterable[str]) -> Path:
        path = self.results_dir / f"{name}_order.csv"
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["rank", "test"])
            for idx, test in enumerate(tests, start=1):
                writer.writerow([idx, test])
        return path

    def compute_apfd(self, order_path: Path) -> float:
        test_map = load_test_map(self.mutants_dir / "testMap.csv")
        killed = load_killed_mutants(self.mutants_dir / "kill.csv")
        cov_map = load_cov_map(self.mutants_dir / "covMap.csv")
        order = load_order(order_path, test_map)
        return compute_apfd(order, test_map, killed, cov_map)

    def run(self) -> Dict[str, float]:
        apfd_results: Dict[str, float] = {}
        t0 = perf_counter()
        total_csv = self.write_order("total", self.total_order())
        t_total = perf_counter()
        apfd_results["total"] = self.compute_apfd(total_csv)
        t_additional_0 = perf_counter()
        additional_csv = self.write_order("additional", self.additional_order())
        t_additional = perf_counter()
        apfd_results["additional"] = self.compute_apfd(additional_csv)

        self.timings = {
            "total": t_total - t0,
            "additional": t_additional - t_additional_0,
        }

        for seed in range(1, 6):
            random_csv = self.write_order(f"random_seed{seed}", self.random_order(seed))
            apfd_results[f"random_seed{seed}"] = self.compute_apfd(random_csv)
        return apfd_results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Сравнение TCP-бенчмарков и расчёт APFD.")
    parser.add_argument("--project", help="Defects4J ID")
    parser.add_argument("--bug", help="bug id")
    parser.add_argument("--timing-csv", help="Куда сохранять тайминги построения порядков (append)")
    return parser.parse_args()


def has_mutants(project: str, bug: str) -> bool:
    base = ROOT / "data" / "raw" / project / bug / "mutants"
    return (base / "testMap.csv").is_file() and (base / "covMap.csv").is_file() and (base / "kill.csv").is_file()


def main() -> None:
    args = parse_args()
    pairs: List[Tuple[str, str]]
    if args.project and args.bug:
        pairs = [(args.project, args.bug)]
    else:
        with (ROOT / "config" / "projects.csv").open(encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            pairs = [(row["project"], row["bug_id"]) for row in reader]

    results = []
    for project, bug in pairs:
        coverage_path = ROOT / "data" / "raw" / project / bug / "coverage" / "matrix.csv"
        if not coverage_path.is_file() or not has_mutants(project, bug):
            continue
        benchmarks = TCPBenchmarks(project, bug)
        apfd_scores = benchmarks.run()
        for mode, apfd in apfd_scores.items():
            results.append({"project": project, "bug": bug, "mode": mode, "apfd": f"{apfd:.4f}"})
        if args.timing_csv:
            timing_path = Path(args.timing_csv)
            timing_path.parent.mkdir(parents=True, exist_ok=True)
            write_header = not timing_path.exists()
            with timing_path.open("a", newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(
                    fh,
                    fieldnames=["project", "bug", "mode", "clusters", "tests", "methods", "duration_sec"],
                )
                if write_header:
                    writer.writeheader()
                for mode, duration in benchmarks.timings.items():
                    writer.writerow(
                        {
                            "project": project,
                            "bug": bug,
                            "mode": f"tcp-{mode}",
                            "clusters": "",
                            "tests": len(benchmarks.coverage.tests),
                            "methods": len(benchmarks.coverage.methods),
                            "duration_sec": f"{duration:.4f}",
                        }
                    )

    output = ROOT / "docs" / "lom_reports" / "tcp_apfd_results.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["project", "bug", "mode", "apfd"])
        writer.writeheader()
        writer.writerows(results)
    print(f"[done] TCP APFD results -> {output}")


if __name__ == "__main__":
    main()

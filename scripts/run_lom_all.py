#!/usr/bin/env python3
"""Расчёт LoM-Score для всех проектов из config/projects.csv."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import List
from time import perf_counter


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Пакетный расчёт LoM-Score")
    parser.add_argument("--lom-fraction", type=float, default=0.25, help="Доля для нижнего квартиля (lom)")
    parser.add_argument("--top", type=int, default=20, help="Сколько верхних тестов сохранять")
    parser.add_argument("--projects", nargs="*", help="Обработать только указанные проекты")
    parser.add_argument("--output", default="data/results/lom", help="Каталог для сохранения csv")
    parser.add_argument("--skip-existing", action="store_true", help="Пропускать проекты, если итоговый файл уже существует")
    parser.add_argument(
        "--mode",
        choices=("lom", "dis-lom", "cov-clustering"),
        default="lom",
        help="Какой алгоритм использовать",
    )
    parser.add_argument("--clusters", type=int, default=0, help="Число кластеров для CovClustering (0 — авто)")
    parser.add_argument("--profile", action="store_true", help="Печатать тайминги CovClustering для каждого запуска")
    parser.add_argument("--timing-csv", help="Сохранять тайминги алгоритмов в указанный CSV (append)")
    return parser.parse_args()


def load_projects(root: Path, filters: List[str] | None) -> List[tuple[str, str]]:
    config = root / "config" / "projects.csv"
    with config.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        rows = [(row["project"], row["bug_id"]) for row in reader]
    if filters:
        filters_set = set(filters)
        rows = [row for row in rows if row[0] in filters_set]
    return rows


def ensure_python_path(root: Path) -> None:
    package_root = root / "lom-study"
    if str(package_root) not in sys.path:
        sys.path.insert(0, str(package_root))


def _effective_clusters(configured: int | None, test_count: int) -> int:
    value = configured or 0
    if value <= 0:
        value = max(2, int(round(test_count ** 0.5)))
    return max(1, min(value, test_count))


def _append_timing(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["project", "bug", "mode", "clusters", "tests", "methods", "duration_sec"]
    write_header = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        writer.writerow(row)


def main() -> None:
    args = parse_args()
    root = Path(__file__).resolve().parents[1]
    ensure_python_path(root)

    from tcp.data_loader import read_coverage_matrix, read_impact_probabilities  # type: ignore
    from tcp.lom_algorithms import compute_dis_lom_scores, compute_lom_scores  # type: ignore
    from tcp.cov_clustering import compute_cov_clustering  # type: ignore

    results_dir = root / args.output
    if args.mode == "cov-clustering" and args.output == "data/results/lom":
        # чтобы не смешивать с результатами LoM по умолчанию
        results_dir = root / "data" / "results" / "cov_clustering"
    rows = load_projects(root, args.projects)

    for project, bug in rows:
        base = root / "data" / "raw" / project / bug
        coverage_path = base / "coverage" / "matrix.csv"
        impact_path = base / "cia" / "impact_probabilities.csv"
        if args.mode == "cov-clustering":
            if not coverage_path.is_file():
                print(f"[skip] {project}-{bug} (нет coverage)")
                continue
        else:
            if not coverage_path.is_file() or not impact_path.is_file():
                print(f"[skip] {project}-{bug} (нет coverage или CIA)")
                continue

        if args.mode == "dis-lom":
            output_name = "dis_lom_scores.csv"
        elif args.mode == "cov-clustering":
            output_name = "cov_clustering_scores.csv"
        else:
            output_name = "lom_scores.csv"

        if args.skip_existing and (results_dir / project / bug / output_name).is_file():
            print(f"[skip] {project}-{bug} ({output_name} уже существует)")
            continue

        coverage = read_coverage_matrix(coverage_path)
        test_count = len(coverage.tests)
        method_count = len(coverage.methods)
        cluster_count = _effective_clusters(args.clusters if args.clusters > 0 else None, test_count) if args.mode == "cov-clustering" else 0

        start_ts = None
        if args.mode == "cov-clustering":
            start_ts = perf_counter()
            clusters = args.clusters if args.clusters > 0 else None
            scores = compute_cov_clustering(coverage, num_clusters=clusters, profile=args.profile)
        else:
            impact = read_impact_probabilities(impact_path)
            start_ts = perf_counter()
            if args.mode == "dis-lom":
                scores = compute_dis_lom_scores(coverage, impact, lom_fraction=args.lom_fraction)
            else:
                scores = compute_lom_scores(coverage, impact, lom_fraction=args.lom_fraction)

        if not scores:
            print(f"[warn] {project}-{bug} — список {args.mode} пуст (нет сопоставлений)")
            continue

        project_dir = results_dir / project / bug
        project_dir.mkdir(parents=True, exist_ok=True)
        output_file = project_dir / output_name
        with output_file.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["rank", "test", "score"])
            for idx, item in enumerate(scores, start=1):
                writer.writerow([idx, item.test_id, f"{item.score:.6f}"])

        top_n = scores[: args.top]
        duration = perf_counter() - start_ts if start_ts is not None else 0.0
        if args.timing_csv:
            timing_path = Path(args.timing_csv)
            _append_timing(
                timing_path,
                {
                    "project": project,
                    "bug": bug,
                    "mode": args.mode,
                    "clusters": cluster_count,
                    "tests": test_count,
                    "methods": method_count,
                    "duration_sec": f"{duration:.4f}",
                },
            )
        print(f"[done] {project}-{bug} → {output_file}")
        # for idx, item in enumerate(top_n, start=1):
            # print(f"    {idx:2d}. {item.test_id} -> {item.score:.6f}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Вычисление LoM-приоритетов для выбранного проекта."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Расчёт LoM-Score на основе CIA и покрытия")
    parser.add_argument("--project", required=True)
    parser.add_argument("--bug", required=True)
    parser.add_argument("--top", type=int, default=10, help="Сколько тестов вывести")
    parser.add_argument("--lom-fraction", type=float, default=0.25, help="Доля тестов для вычисления lom")
    parser.add_argument(
        "--mode",
        choices=("lom", "dis-lom", "mwdm-tga", "mwdm-aga", "cov-clustering"),
        default="lom",
        help="Алгоритм: LoM, Dis-LoM, MWDM-TGA, MWDM-AGA или CovClustering",
    )
    parser.add_argument(
        "--callgraph",
        default="callgraph.txt",
        help="Путь к callgraph.txt внутри CIA директории (для MWDM)",
    )
    parser.add_argument(
        "--clusters",
        type=int,
        default=0,
        help="Количество кластеров для CovClustering (0 — выбрать автоматически)",
    )
    parser.add_argument("--profile", action="store_true", help="Печатать тайминги CovClustering")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    root = Path(__file__).resolve().parents[1]

    sys.path.insert(0, str(root / "lom-study"))

    from tcp.data_loader import read_coverage_matrix, read_impact_probabilities  # type: ignore
    from tcp.lom_algorithms import compute_dis_lom_scores, compute_lom_scores  # type: ignore
    from tcp.mwdm_algorithms import (  # type: ignore
        compute_mwdm_aga_scores,
        compute_mwdm_tga_scores,
        compute_mwdm_weights,
        _weights_for_coverage_methods,
    )
    from tcp.cov_clustering import compute_cov_clustering  # type: ignore
    base = root / "data" / "raw" / args.project / args.bug

    coverage_path = base / "coverage" / "matrix.csv"
    impact_path = base / "cia" / "impact_probabilities.csv"
    callgraph_path = base / "cia" / args.callgraph

    coverage = read_coverage_matrix(coverage_path)
    if args.mode in ("mwdm-tga", "mwdm-aga"):
        method_weights = compute_mwdm_weights(callgraph_path)
        weights_for_coverage = _weights_for_coverage_methods(coverage, method_weights)
        if args.mode == "mwdm-tga":
            results = compute_mwdm_tga_scores(coverage, weights_for_coverage)
        else:
            results = compute_mwdm_aga_scores(coverage, weights_for_coverage)
    elif args.mode == "cov-clustering":
        clusters = args.clusters if args.clusters > 0 else None
        results = compute_cov_clustering(coverage, num_clusters=clusters, profile=args.profile)
    else:
        impact = read_impact_probabilities(impact_path)
        if args.mode == "dis-lom":
            results = compute_dis_lom_scores(coverage, impact, lom_fraction=args.lom_fraction)
        else:
            results = compute_lom_scores(coverage, impact, lom_fraction=args.lom_fraction)

    if not results:
        print("[warn] Не удалось вычислить LoM-приоритеты (проверьте сопоставление методов)")
        return

    top_results = results[: args.top]
    for idx, result in enumerate(top_results, start=1):
        print(f"{idx:3d}. {result.test_id} -> {result.score:.6f}")


if __name__ == "__main__":
    main()

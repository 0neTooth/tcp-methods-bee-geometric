from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import List, Sequence
from time import perf_counter
import sys

import numpy as np

try:
    from sklearn.cluster import AgglomerativeClustering

    _SKLEARN_AVAILABLE = True
except Exception:
    _SKLEARN_AVAILABLE = False

from .data_loader import CoverageMatrix


@dataclass
class CovClusteringResult:
    test_id: str
    score: float


def compute_cov_clustering(
    coverage: CoverageMatrix,
    num_clusters: int | None = None,
    distance: str = "euclidean",
    profile: bool = False,
) -> List[CovClusteringResult]:
    if not coverage.tests:
        return []

    t0 = perf_counter()
    test_count = len(coverage.tests)
    num_clusters = _normalize_clusters(num_clusters, test_count)
    coverage_sets = [_row_to_set(row) for row in coverage.hits]
    X = np.asarray(coverage.hits, dtype=float)
    t_cov_sets = perf_counter()

    if _SKLEARN_AVAILABLE and distance == "euclidean":
        clusters = _agglomerative_sklearn(X, num_clusters)
        t_dist = t_cov_sets
        t_cluster = perf_counter()
        backend = "sklearn"
    else:
        dist_matrix = _distance_matrix_fast(X, metric=distance)
        t_dist = perf_counter()
        clusters = _agglomerative_average(dist_matrix.tolist(), num_clusters)
        t_cluster = perf_counter()
        backend = "fallback"

    # Additional приоритизация внутри каждого кластера
    cluster_orders: List[List[int]] = [
        _additional_order(cluster, coverage_sets) for cluster in clusters
    ]
    t_intra = perf_counter()

    # Round-robin: выбираем по одному из каждого кластера и упорядочиваем Total внутри раунда
    ordered_indices: List[int] = []
    round_idx = 0
    while len(ordered_indices) < test_count:
        round_candidates = [order[round_idx] for order in cluster_orders if round_idx < len(order)]
        if not round_candidates:
            break
        round_order = _total_order(round_candidates, coverage_sets, coverage.tests)
        ordered_indices.extend(round_order)
        round_idx += 1

    t_end = perf_counter()
    results = [
        CovClusteringResult(
            test_id=coverage.tests[idx],
            score=float(len(coverage_sets[idx])),
        )
        for idx in ordered_indices
    ]

    if profile:
        timings = {
            "coverage_sets": t_cov_sets - t0,
            "distance_matrix": t_dist - t_cov_sets,
            "clustering": t_cluster - t_dist,
            "intra_additional": t_intra - t_cluster,
            "round_robin": t_end - t_intra,
            "total": t_end - t0,
        }
        _log_timings(test_count=test_count, num_clusters=num_clusters, timings=timings)
    return results


def _normalize_clusters(num_clusters: int | None, test_count: int) -> int:
    if num_clusters is None or num_clusters <= 0:
        # простая эвристика: корень из количества тестов, но не меньше 2
        num_clusters = max(2, int(round(test_count ** 0.5)))
    return max(1, min(num_clusters, test_count))


def _row_to_set(row: Sequence[int]) -> set[int]:
    return {idx for idx, value in enumerate(row) if value}


def _distance_matrix(rows: List[Sequence[int]], metric: str = "euclidean") -> List[List[float]]:
    if metric != "euclidean":
        raise ValueError(f"Unsupported distance metric: {metric}")
    n = len(rows)
    matrix = [[0.0 for _ in range(n)] for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            dist = _euclidean(rows[i], rows[j])
            matrix[i][j] = dist
            matrix[j][i] = dist
    return matrix


def _euclidean(a: Sequence[int], b: Sequence[int]) -> float:
    return sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def _distance_matrix_fast(X: np.ndarray, metric: str = "euclidean") -> np.ndarray:
    if metric != "euclidean":
        raise ValueError(f"Unsupported distance metric: {metric}")
    # Используем ||a-b||^2 = ||a||^2 + ||b||^2 - 2*a·b
    X = np.asarray(X, dtype=float)
    norms = np.sum(X * X, axis=1)
    dist_sq = norms[:, None] + norms[None, :] - 2.0 * X.dot(X.T)
    # численная стабильность
    np.maximum(dist_sq, 0.0, out=dist_sq)
    return np.sqrt(dist_sq, dtype=float)


def _agglomerative_average(dist_matrix: List[List[float]], target_clusters: int) -> List[List[int]]:
    """
    Простая агломеративная кластеризация с average linkage на основе предвычисленной матрицы расстояний.
    """
    n = len(dist_matrix)
    clusters: List[List[int]] = [[i] for i in range(n)]
    if n == 0 or target_clusters >= n:
        return clusters

    while len(clusters) > target_clusters:
        best_pair = None
        best_dist = float("inf")
        for i in range(len(clusters)):
            for j in range(i + 1, len(clusters)):
                dist = _average_linkage_distance(clusters[i], clusters[j], dist_matrix)
                if dist < best_dist:
                    best_dist = dist
                    best_pair = (i, j)
        if best_pair is None:
            break
        i, j = best_pair
        merged = clusters[i] + clusters[j]
        new_clusters = []
        for idx, cluster in enumerate(clusters):
            if idx in best_pair:
                continue
            new_clusters.append(cluster)
        new_clusters.append(merged)
        clusters = new_clusters

    # фиксируем порядок кластеров для детерминизма
    clusters.sort(key=lambda c: min(c))
    return clusters


def _agglomerative_sklearn(X: np.ndarray, target_clusters: int) -> List[List[int]]:
    if target_clusters <= 1 or len(X) <= target_clusters:
        return [[i] for i in range(len(X))]
    try:
        model = AgglomerativeClustering(
            n_clusters=target_clusters,
            linkage="average",
            metric="euclidean",
        )
    except TypeError:
        # совместимость со старыми версиями sklearn, где используется affinity
        model = AgglomerativeClustering(
            n_clusters=target_clusters,
            linkage="average",
            affinity="euclidean",
        )
    labels = model.fit_predict(X)
    clusters: List[List[int]] = []
    for label in sorted(set(labels)):
        indices = [idx for idx, lbl in enumerate(labels) if lbl == label]
        clusters.append(indices)
    # детерминируем порядок внутри кластера
    for cluster in clusters:
        cluster.sort()
    clusters.sort(key=lambda c: c[0])
    return clusters


def _average_linkage_distance(a: List[int], b: List[int], dist_matrix: List[List[float]]) -> float:
    total = 0.0
    count = 0
    for i in a:
        for j in b:
            total += dist_matrix[i][j]
            count += 1
    return total / count if count else 0.0


def _additional_order(indices: List[int], coverage_sets: List[set[int]]) -> List[int]:
    if not indices:
        return []
    remaining_methods = set().union(*(coverage_sets[i] for i in indices))
    unused = set(indices)
    ordered: List[int] = []

    while remaining_methods and unused:
        best_idx = None
        best_gain = -1
        for idx in sorted(unused):
            gain = len(coverage_sets[idx] & remaining_methods)
            if gain > best_gain:
                best_gain = gain
                best_idx = idx
        if best_idx is None:
            break
        ordered.append(best_idx)
        unused.remove(best_idx)
        remaining_methods -= coverage_sets[best_idx]

    ordered.extend(sorted(unused))
    return ordered


def _total_order(indices: List[int], coverage_sets: List[set[int]], test_names: Sequence[str]) -> List[int]:
    return [
        idx
        for _, _, idx in sorted(
            ((len(coverage_sets[idx]), test_names[idx], idx) for idx in indices),
            key=lambda item: (-item[0], item[1]),
        )
    ]


def _log_timings(test_count: int, num_clusters: int, timings: dict[str, float]) -> None:
    lines = [
        "[profile] CovClustering:",
        f"    tests={test_count}, clusters={num_clusters}",
    ]
    if _SKLEARN_AVAILABLE:
        lines.append("    backend=sklearn")
    else:
        lines.append("    backend=fallback")
    for name, value in timings.items():
        lines.append(f"    {name}: {value:.3f}s")
    sys.stderr.write("\n".join(lines) + "\n")

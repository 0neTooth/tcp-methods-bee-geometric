from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

from .data_loader import (
    CoverageMatrix,
    coverage_signature,
    callgraph_signature_to_method,
    parse_callgraph,
)


@dataclass
class MwdmResult:
    test_id: str
    score: float


def _build_method_graph(callgraph_path) -> Dict[str, List[str]]:
    edges = parse_callgraph(callgraph_path)
    graph: Dict[str, List[str]] = defaultdict(list)
    for raw_caller, raw_callee in edges:
        caller_owner, caller_method, caller_params = callgraph_signature_to_method(raw_caller)
        callee_owner, callee_method, callee_params = callgraph_signature_to_method(raw_callee)
        if not caller_owner or not callee_owner:
            continue
        caller_sig = f"{caller_owner}.{caller_method}({','.join(caller_params)})"
        callee_sig = f"{callee_owner}.{callee_method}({','.join(callee_params)})"
        graph[caller_sig].append(callee_sig)
        # добавляем вершину без исходящих, чтобы не потерять её при отсутствии входящих рёбер
        graph.setdefault(callee_sig, [])
    return graph


def _compute_reachability_weights(graph: Dict[str, List[str]]) -> Dict[str, float]:
    memo: Dict[str, int] = {}

    def dfs(node: str) -> int:
        if node in memo:
            return memo[node]
        seen = set()  # тип: ignore[var-annotated]
        stack = list(graph.get(node, []))
        while stack:
            nxt = stack.pop()
            if nxt in seen:
                continue
            seen.add(nxt)
            stack.extend(graph.get(nxt, []))
        memo[node] = len(seen)
        return memo[node]

    raw_counts = {node: dfs(node) for node in graph.keys()}
    if not raw_counts:
        return {}
    max_count = max(raw_counts.values())
    if max_count <= 0:
        return {k: 0.1 for k in raw_counts}
    return {k: 0.1 + (0.8 * (v / max_count)) for k, v in raw_counts.items()}


def _weights_for_coverage_methods(coverage: CoverageMatrix, weights: Dict[str, float]) -> List[float]:
    result: List[float] = []
    for raw_method in coverage.methods:
        sig = coverage_signature(raw_method)
        result.append(weights.get(sig, 0.0))
    return result


def compute_mwdm_weights(callgraph_path) -> Dict[str, float]:
    graph = _build_method_graph(callgraph_path)
    return _compute_reachability_weights(graph)


def compute_mwdm_tga_scores(
    coverage: CoverageMatrix,
    method_weights: Sequence[float],
) -> List[MwdmResult]:
    if not coverage.tests:
        return []
    scores: List[Tuple[str, float]] = []
    for test_id, row in zip(coverage.tests, coverage.hits):
        score = sum(hit * weight for hit, weight in zip(row, method_weights))
        scores.append((test_id, score))
    scores.sort(key=lambda item: item[1], reverse=True)
    return [MwdmResult(test_id=test_id, score=score) for test_id, score in scores]


def compute_mwdm_aga_scores(
    coverage: CoverageMatrix,
    method_weights: Sequence[float],
) -> List[MwdmResult]:
    if not coverage.tests:
        return []
    remaining_indices = list(range(len(coverage.tests)))
    available_weights = list(method_weights)
    ordered: List[MwdmResult] = []

    while remaining_indices:
        best_idx = None
        best_score = -1.0
        for idx in remaining_indices:
            row = coverage.hits[idx]
            score = sum(hit * weight for hit, weight in zip(row, available_weights))
            if score > best_score:
                best_score = score
                best_idx = idx
        if best_idx is None:
            break

        test_id = coverage.tests[best_idx]
        ordered.append(MwdmResult(test_id=test_id, score=best_score))

        # обнуляем веса покрытых методов, чтобы учитывать только новые методы в следующих шагах
        for col, hit in enumerate(coverage.hits[best_idx]):
            if hit:
                available_weights[col] = 0.0

        remaining_indices.remove(best_idx)

    return ordered

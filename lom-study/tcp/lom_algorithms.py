from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Dict, Set, Tuple

from .data_loader import CoverageMatrix, ImpactProbabilities, coverage_signature


@dataclass
class LomResult:
    test_id: str
    score: float


@dataclass
class LomProfile:
    test_id: str
    base_score: float
    impacted_methods: Set[int]


def coverage_to_impact_mapping(coverage: CoverageMatrix, impact: ImpactProbabilities) -> Dict[int, float]:
    mapping: Dict[int, float] = {}
    for idx, raw_name in enumerate(coverage.methods):
        sig = coverage_signature(raw_name)
        probability = impact.methods.get(sig)
        if probability is None:
            continue
        mapping[idx] = probability
    return mapping


def compute_lom_scores(
    coverage: CoverageMatrix,
    impact: ImpactProbabilities,
    lom_fraction: float = 0.25,
) -> list[LomResult]:
    profiles = _compute_lom_profiles(coverage, impact, lom_fraction)
    if not profiles:
        return [LomResult(test_id=test, score=0.0) for test in coverage.tests]
    sorted_profiles = sorted(profiles, key=lambda profile: profile.base_score, reverse=True)
    return [LomResult(test_id=profile.test_id, score=profile.base_score) for profile in sorted_profiles]


def compute_dis_lom_scores(
    coverage: CoverageMatrix,
    impact: ImpactProbabilities,
    lom_fraction: float = 0.25,
) -> list[LomResult]:
    profiles = _compute_lom_profiles(coverage, impact, lom_fraction)
    if not profiles:
        return [LomResult(test_id=test, score=0.0) for test in coverage.tests]

    remaining = profiles.copy()
    selected: list[LomProfile] = []
    ordered: list[LomResult] = []

    while remaining:
        best_profile = None
        best_adjusted = -1.0
        for profile in remaining:
            penalty = 0.0
            if selected:
                penalty = max(_jaccard(profile.impacted_methods, sel.impacted_methods) for sel in selected)
            adjusted = profile.base_score * (1.0 - penalty)
            if adjusted > best_adjusted or (adjusted == best_adjusted and (best_profile is None or profile.base_score > best_profile.base_score)):
                best_profile = profile
                best_adjusted = adjusted

        if best_profile is None:
            break

        ordered.append(LomResult(test_id=best_profile.test_id, score=best_adjusted))
        selected.append(best_profile)
        remaining.remove(best_profile)

    return ordered


def _compute_lom_profiles(
    coverage: CoverageMatrix,
    impact: ImpactProbabilities,
    lom_fraction: float,
) -> list[LomProfile]:
    mapping = coverage_to_impact_mapping(coverage, impact)
    if not mapping:
        profiles = [
            LomProfile(test_id=test, base_score=0.0, impacted_methods=set())
            for test in coverage.tests
        ]
        return _aggregate_profiles(profiles)

    impacted_sets: list[Set[int]] = []
    for row in coverage.hits:
        impacted = {idx for idx, value in enumerate(row) if value and idx in mapping}
        impacted_sets.append(impacted)

    non_zero_counts = [len(s) for s in impacted_sets if s]
    if not non_zero_counts:
        profiles = [
            LomProfile(test_id=test, base_score=0.0, impacted_methods=impacted)
            for test, impacted in zip(coverage.tests, impacted_sets)
        ]
        return _aggregate_profiles(profiles)

    sorted_counts = sorted(non_zero_counts)
    index = int(len(sorted_counts) * lom_fraction)
    if index >= len(sorted_counts):
        index = len(sorted_counts) - 1
    lom_value = max(1, sorted_counts[index])

    profiles: list[LomProfile] = []
    for test_id, row, impacted in zip(coverage.tests, coverage.hits, impacted_sets):
        if not impacted:
            profiles.append(LomProfile(test_id=test_id, base_score=0.0, impacted_methods=set()))
            continue
        probabilities = sorted([mapping[idx] for idx in impacted], reverse=True)
        top = probabilities[:lom_value]
        base_score = mean(top) if top else 0.0
        profiles.append(LomProfile(test_id=test_id, base_score=base_score, impacted_methods=impacted))
    return _aggregate_profiles(profiles)


def _jaccard(a: Set[int], b: Set[int]) -> float:
    if not a and not b:
        return 0.0
    intersection = len(a & b)
    if intersection == 0:
        return 0.0
    union = len(a | b)
    if union == 0:
        return 0.0
    return intersection / union


def _aggregate_profiles(profiles: list[LomProfile]) -> list[LomProfile]:
    aggregated: dict[str, LomProfile] = {}
    for profile in profiles:
        existing = aggregated.get(profile.test_id)
        if existing is None:
            aggregated[profile.test_id] = profile
        else:
            combined_methods = existing.impacted_methods | profile.impacted_methods
            combined_score = max(existing.base_score, profile.base_score)
            aggregated[profile.test_id] = LomProfile(
                test_id=profile.test_id,
                base_score=combined_score,
                impacted_methods=combined_methods,
            )
    return list(aggregated.values())

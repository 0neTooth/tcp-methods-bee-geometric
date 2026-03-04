"""Aggregate APFD results across LoM/Dis-LoM and TCP benchmarks."""

from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_apfd(path: Path) -> dict[tuple[str, str], dict[str, float]]:
    mapping: dict[tuple[str, str], dict[str, float]] = {}
    with path.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            key = (row["project"], row["bug"])
            mapping.setdefault(key, {})[row["mode"]] = float(row["apfd"])
    return mapping


def best_tcp_modes(tcp_scores: dict[str, float]) -> tuple[str, float, float]:
    candidates = {k: v for k, v in tcp_scores.items() if k in {"total", "additional"}}
    if not candidates:
        return "", 0.0, float("nan")
    best_mode = max(candidates, key=candidates.get)
    random_scores = [tcp_scores[k] for k in tcp_scores if k.startswith("random_seed")]
    avg_random = sum(random_scores) / len(random_scores) if random_scores else float("nan")
    return best_mode, candidates[best_mode], avg_random


def main() -> None:
    lom_path = ROOT / "docs" / "lom_reports" / "apfd_results.csv"
    tcp_path = ROOT / "docs" / "lom_reports" / "tcp_apfd_results.csv"
    output_path = ROOT / "docs" / "lom_reports" / "apfd_summary.csv"

    lom_data = load_apfd(lom_path)
    tcp_data = load_apfd(tcp_path)

    rows = []
    for key in sorted(tcp_data.keys()):
        project, bug = key
        lom_scores = lom_data.get(key, {})
        tcp_scores = tcp_data[key]

        lom_apfd = lom_scores.get("lom")
        dis_apfd = lom_scores.get("dis-lom")
        best_lom_value, best_lom_label = None, ""
        if lom_apfd is not None or dis_apfd is not None:
            if dis_apfd is not None and lom_apfd is not None:
                if dis_apfd >= lom_apfd:
                    best_lom_value, best_lom_label = dis_apfd, "Dis-LoM"
                else:
                    best_lom_value, best_lom_label = lom_apfd, "LoM"
            elif dis_apfd is not None:
                best_lom_value, best_lom_label = dis_apfd, "Dis-LoM"
            elif lom_apfd is not None:
                best_lom_value, best_lom_label = lom_apfd, "LoM"

        best_tcp_mode, best_tcp_apfd, avg_random = best_tcp_modes(tcp_scores)

        rows.append({
            "project": project,
            "bug": bug,
            "lom_apfd": f"{lom_apfd:.4f}" if lom_apfd is not None else "",
            "dis_lom_apfd": f"{dis_apfd:.4f}" if dis_apfd is not None else "",
            "best_lom_family": best_lom_label,
            "best_lom_apfd": f"{best_lom_value:.4f}" if best_lom_value is not None else "",
            "best_tcp_mode": best_tcp_mode,
            "best_tcp_apfd": f"{best_tcp_apfd:.4f}" if best_tcp_mode else "",
            "random_mean": f"{avg_random:.4f}" if avg_random == avg_random else "",
        })

    with output_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=[
            "project", "bug",
            "lom_apfd", "dis_lom_apfd",
            "best_lom_family", "best_lom_apfd",
            "best_tcp_mode", "best_tcp_apfd",
            "random_mean",
        ])
        writer.writeheader()
        writer.writerows(rows)

    print(f"[done] APFD summary -> {output_path}")


if __name__ == "__main__":
    main()

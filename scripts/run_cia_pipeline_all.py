#!/usr/bin/env python3
"""Запускает CIA-пайплайн для всех проектов из config/projects.csv."""

from __future__ import annotations

import argparse
import csv
import subprocess
import sys
from pathlib import Path
from typing import Iterable, Optional


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Пакетный запуск CIA-пайплайна по всем проектам")
    parser.add_argument("--skip-compile", action="store_true", help="Пробрасывать --skip-compile внутрь run_cia_pipeline")
    parser.add_argument("--classpath", help="Кастомный classpath для инструментов CIA")
    parser.add_argument("--rebuild-dist", action="store_true", help="Запускать installDist перед каждым проектом")
    parser.add_argument("--projects", nargs="*", help="Ограничиться подмножеством проектов")
    parser.add_argument("--resume-from", help="Пропускать проекты пока не дойдём до указанного (формат Project:Bug)")
    parser.add_argument("--skip-existing", action="store_true", help="Пропускать проекты, где impact_probabilities.csv уже есть")
    return parser.parse_args()


def run_cmd(cmd: Iterable[str], cwd: Optional[Path] = None) -> None:
    cmd_list = [str(item) for item in cmd]
    print(f"[run] {' '.join(cmd_list)}")
    subprocess.run(cmd_list, cwd=str(cwd) if cwd else None, check=True)


def main() -> None:
    args = parse_args()
    root = Path(__file__).resolve().parents[1]
    config_path = root / "config" / "projects.csv"

    with config_path.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)

    if args.projects:
        allowed = set(args.projects)
        rows = [row for row in rows if row["project"] in allowed]

    resume = None
    if args.resume_from:
        resume = args.resume_from.strip()

    for row in rows:
        project = row["project"]
        bug = row["bug_id"]
        key = f"{project}:{bug}"

        if resume:
            if key == resume:
                resume = None
            else:
                print(f"[skip] {key} (до resume)")
                continue

        impact_file = root / "data" / "raw" / project / bug / "cia" / "impact_probabilities.csv"
        if args.skip_existing and impact_file.is_file():
            print(f"[skip] {key} (impact_probabilities.csv уже существует)")
            continue

        cmd = [
            sys.executable,
            str(root / "scripts" / "run_cia_pipeline.py"),
            "--project",
            project,
            "--bug",
            bug,
        ]
        if args.skip_compile:
            cmd.append("--skip-compile")
        if args.classpath:
            cmd.extend(["--classpath", args.classpath])
        if args.rebuild_dist:
            cmd.append("--rebuild-dist")

        try:
            run_cmd(cmd, cwd=root)
        except subprocess.CalledProcessError as exc:
            print(f"[error] Проект {key} завершился ошибкой (код {exc.returncode}). Продолжаем.")

    print("[done] Пакетный запуск CIA завершён")


if __name__ == "__main__":
    main()

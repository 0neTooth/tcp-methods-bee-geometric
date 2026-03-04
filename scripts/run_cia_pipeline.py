#!/usr/bin/env python3
"""
Комплексный запуск CIA-пайплайна (ROC -> forward slicing -> Markov).

Пример:
    python scripts/run_cia_pipeline.py --project Jsoup --bug 93
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Iterable, Optional

from run_cia_roc import (  # type: ignore
    build_distribution,
    java_pathsep,
    locate_classpath,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Полный запуск CIA-анализа для проекта Defects4J.")
    parser.add_argument("--project", required=True, help="Имя проекта (например, Jsoup)")
    parser.add_argument("--bug", required=True, help="ID бага (например, 93)")
    parser.add_argument(
        "--include-file",
        help="Файл с префиксами (по умолчанию data/raw/<project>/<bug>/cia/modified_classes.src)",
    )
    parser.add_argument(
        "--skip-roc",
        action="store_true",
        help="Пропустить этап генерации roc.csv (ожидается, что файл уже существует)",
    )
    parser.add_argument(
        "--skip-slicing",
        action="store_true",
        help="Пропустить запуск forward slicing (ожидается готовый forward_slicing.csv)",
    )
    parser.add_argument(
        "--skip-markov",
        action="store_true",
        help="Пропустить расчёт impact_probabilities.csv",
    )
    parser.add_argument(
        "--skip-compile",
        action="store_true",
        help="Передать --skip-compile в run_cia_roc.py",
    )
    parser.add_argument(
        "--classpath",
        help="Путь к classpath (jar или каталог с *.jar) для модулей CIA, если нужно переопределить",
    )
    parser.add_argument(
        "--rebuild-dist",
        action="store_true",
        help="Принудительно выполнить gradle installDist перед запуском",
    )
    return parser.parse_args()


def run_cmd(cmd: Iterable[str], cwd: Optional[Path] = None, env: Optional[dict] = None) -> None:
    cmd_list = [str(part) for part in cmd]
    print(f"[run] {' '.join(cmd_list)}")
    subprocess.run(cmd_list, cwd=str(cwd) if cwd else None, check=True, env=env)


def find_classes_dir(version_dir: Path) -> Optional[Path]:
    candidates = [
        version_dir / "target" / "classes",
        version_dir / "build" / "classes" / "java" / "main",
        version_dir / "build" / "classes" / "main",
        version_dir / "build" / "classes",
        version_dir / "classes",
        version_dir / "out" / "production" / "classes",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def ensure_classpath(root: Path, explicit: Optional[str], rebuild: bool) -> str:
    if rebuild:
        build_distribution(root)
    try:
        return locate_classpath(root, explicit)
    except FileNotFoundError:
        build_distribution(root)
        return locate_classpath(root, explicit)


def main() -> None:
    args = parse_args()
    root = Path(__file__).resolve().parents[1]
    project_dir = root / "data" / "raw" / args.project
    fixed_dir = project_dir / f"{args.bug}f"
    buggy_dir = project_dir / f"{args.bug}b"
    cia_dir = project_dir / str(args.bug) / "cia"

    if not fixed_dir.is_dir() or not buggy_dir.is_dir():
        raise FileNotFoundError("Ожидаемые директории buggy/fixed не найдены. Проверьте данные Defects4J.")

    include_file = Path(args.include_file).resolve() if args.include_file else cia_dir / "modified_classes.src"
    if include_file.exists():
        print(f"[info] Используем файл префиксов: {include_file}")
    else:
        print(f"[warn] Файл префиксов не найден ({include_file}); этапы будут выполняться без фильтра.")
        include_file = None

    env = os.environ.copy()

    if not args.skip_roc:
        roc_cmd = [
            sys.executable,
            str(root / "scripts" / "run_cia_roc.py"),
            "--project",
            args.project,
            "--bug",
            args.bug,
        ]
        if include_file:
            roc_cmd.extend(["--include-file", str(include_file)])
        if args.skip_compile:
            roc_cmd.append("--skip-compile")
        if args.classpath:
            roc_cmd.extend(["--classpath", args.classpath])
        if args.rebuild_dist:
            roc_cmd.append("--rebuild-jar")
        run_cmd(roc_cmd, cwd=root, env=env)

    classpath = ensure_classpath(root, args.classpath, args.rebuild_dist)

    fixed_classes = find_classes_dir(fixed_dir)
    if not fixed_classes:
        raise FileNotFoundError(f"Каталог классов фикс-версии не найден: {fixed_dir}")

    if not args.skip_slicing:
        output_csv = cia_dir / "forward_slicing.csv"
        os.makedirs(output_csv.parent, exist_ok=True)
        slicing_cmd = [
            "java",
            "-cp",
            f"{classpath}{java_pathsep()}{fixed_classes}",
            "dev.mpr.cia.SootForwardSlicer",
            str(fixed_classes),
        ]
        if include_file:
            slicing_cmd.append(str(include_file))
        slicing_cmd.append(str(output_csv))
        run_cmd(slicing_cmd, cwd=root, env=env)

    if not args.skip_markov:
        markov_cmd = [
            sys.executable,
            str(root / "scripts" / "run_cia_markov.py"),
            "--project",
            args.project,
            "--bug",
            args.bug,
        ]
        run_cmd(markov_cmd, cwd=root, env=env)

    print("[done] CIA-пайплайн завершён успешно.")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        sys.exit(exc.returncode)
    except Exception as exc:  # pylint: disable=broad-except
        print(f"[error] {exc}", file=sys.stderr)
        sys.exit(1)

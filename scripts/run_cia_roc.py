#!/usr/bin/env python3
"""
Запуск ROC-экспортера для пары версий Defects4J.

Пример:
    python scripts/run_cia_roc.py --project Jsoup --bug 93
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Iterable, Optional


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Генерация roc.csv для пары buggy/fixed классов.")
    parser.add_argument("--project", required=True, help="Имя проекта (каталог в data/raw)")
    parser.add_argument("--bug", required=True, help="Идентификатор бага (например, 93)")
    parser.add_argument(
        "--include-file",
        help="Файл с префиксами (по умолчанию data/raw/<project>/<bug>/cia/modified_classes.src)",
    )
    parser.add_argument(
        "--skip-compile",
        action="store_true",
        help="Не вызывать defects4j compile (ожидается, что классы уже собраны)",
    )
    parser.add_argument(
        "--rebuild-jar",
        action="store_true",
        help="Принудительно пересобрать lom-study (installDist) перед запуском",
    )
    parser.add_argument(
        "--classpath",
        help="Путь к classpath (jar или каталог lib), по умолчанию build/install/lom-study/lib",
    )
    return parser.parse_args()


def run_cmd(cmd: Iterable[str], cwd: Optional[Path] = None) -> None:
    cmd_list = [str(part) for part in cmd]
    print(f"[run] {' '.join(cmd_list)}")
    subprocess.run(cmd_list, cwd=str(cwd) if cwd else None, check=True)


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


def ensure_classes(version_dir: Path, label: str, skip_compile: bool) -> Path:
    classes_dir = find_classes_dir(version_dir)
    if classes_dir:
        return classes_dir
    if skip_compile:
        raise RuntimeError(f"Классы не найдены в {version_dir}; компиляция запрещена (--skip-compile).")
    run_cmd(["defects4j", "compile"], cwd=version_dir)
    classes_dir = find_classes_dir(version_dir)
    if classes_dir:
        return classes_dir
    raise RuntimeError(f"Не удалось найти классы {label} после компиляции в {version_dir}")


def locate_classpath(root: Path, explicit: Optional[str]) -> str:
    if explicit:
        cp_path = Path(explicit).expanduser().resolve()
        if not cp_path.exists():
            raise FileNotFoundError(f"Указанный classpath не найден: {cp_path}")
        if cp_path.is_dir():
            jars = sorted(cp_path.glob("*.jar"))
            return java_classpath(jars)
        return str(cp_path)

    install_lib = root / "lom-study" / "build" / "install" / "lom-study" / "lib"
    if install_lib.exists():
        jars = sorted(install_lib.glob("*.jar"))
        if jars:
            return java_classpath(jars)

    libs_dir = root / "lom-study" / "build" / "libs"
    jars = sorted(libs_dir.glob("lom-study-*.jar"))
    if jars:
        return str(jars[0])
    raise FileNotFoundError("Не найдено jar-файлов lom-study; выполните gradle installDist")


def java_classpath(jars: Iterable[Path]) -> str:
    parts = [str(jar) for jar in jars]
    return java_pathsep().join(parts)


def java_pathsep() -> str:
    return ';' if sys.platform.startswith('win') else ':'


def build_distribution(root: Path) -> None:
    gradlew = root / "gradlew"
    if gradlew.exists():
        cmd = [gradlew, ":lom-study:installDist"]
    else:
        if shutil.which("gradle") is None:
            raise RuntimeError("Не найден gradle; добавьте gradle в PATH или gradlew в корень проекта.")
        cmd = ["gradle", ":lom-study:installDist"]
    run_cmd(cmd, cwd=root)


def main() -> None:
    args = parse_args()
    root = Path(__file__).resolve().parents[1]

    project_dir = root / "data" / "raw" / args.project
    buggy_dir = project_dir / f"{args.bug}b"
    fixed_dir = project_dir / f"{args.bug}f"
    cia_dir = project_dir / str(args.bug) / "cia"

    if not buggy_dir.is_dir():
        raise FileNotFoundError(f"Не найдена баггий версия: {buggy_dir}")
    if not fixed_dir.is_dir():
        raise FileNotFoundError(f"Не найдена фикс-версия: {fixed_dir}")

    include_file = Path(args.include_file).resolve() if args.include_file else cia_dir / "modified_classes.src"
    if include_file.exists():
        print(f"[info] Используем файл префиксов: {include_file}")
    else:
        print(f"[warn] Файл префиксов не найден ({include_file}); экспорт будет без фильтра.")
        include_file = None

    buggy_classes = ensure_classes(buggy_dir, "buggy", args.skip_compile)
    fixed_classes = ensure_classes(fixed_dir, "fixed", args.skip_compile)

    if args.rebuild_jar:
        build_distribution(root)
    try:
        classpath = locate_classpath(root, args.classpath)
    except FileNotFoundError:
        build_distribution(root)
        classpath = locate_classpath(root, args.classpath)

    output_csv = cia_dir / "roc.csv"
    os.makedirs(output_csv.parent, exist_ok=True)

    cmd = [
        "java",
        "-cp",
        classpath,
        "dev.mpr.cia.RocExporterMain",
        str(buggy_classes),
        str(fixed_classes),
        str(output_csv),
    ]
    if include_file:
        cmd.append(str(include_file))

    run_cmd(cmd, cwd=root)
    print(f"[done] ROC сохранён в {output_csv}")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        sys.exit(exc.returncode)
    except Exception as exc:  # pylint: disable=broad-except
        print(f"[error] {exc}", file=sys.stderr)
        sys.exit(1)

#!/usr/bin/env python3
"""Helper utilities for running Defects4J-related commands."""

from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path
from typing import Iterable, Mapping, MutableMapping, Sequence

ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT_DIR / "scripts"


def path_separator() -> str:
    return ";" if os.name == "nt" else ":"


def run_cmd(
    cmd: Sequence[object],
    *,
    cwd: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> None:
    cmd_list = [str(part) for part in cmd]
    printable = " ".join(shlex.quote(part) for part in cmd_list)
    print(f"[run] {printable}")
    subprocess.run(
        cmd_list,
        check=True,
        cwd=str(cwd) if cwd else None,
        env=dict(env) if env is not None else None,
    )


def defects4j_export(workdir: Path, key: str, env: Mapping[str, str] | None = None) -> str:
    result = subprocess.check_output(
        ["defects4j", "export", "-p", key],
        cwd=str(workdir),
        env=dict(env) if env is not None else None,
    )
    return result.decode().strip()


def join_classpath(parts: Iterable[object]) -> str:
    cleaned = [str(part) for part in parts if part]
    return path_separator().join(cleaned)


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


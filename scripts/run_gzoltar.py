#!/usr/bin/env python3
"""Run GZoltar to collect coverage and export matrix.csv."""

from __future__ import annotations

import argparse
import os
import shlex
import shutil
import sys
from pathlib import Path

from pipeline_utils import ROOT_DIR, ensure_dir, defects4j_export, join_classpath, run_cmd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect coverage with GZoltar for a Defects4J project/bug.")
    parser.add_argument("project", help="Defects4J project id (e.g., Jsoup)")
    parser.add_argument("bug_id", help="Bug identifier (e.g., 93)")
    parser.add_argument(
        "--gzoltar-home",
        default=None,
        help="Directory containing gzoltarcli.jar and gzoltaragent.jar "
        "(default: tools/gzoltar or $GZOLTAR_HOME).",
    )
    parser.add_argument("--includes", default=None, help="Include filter for instrumentation (default: *)")
    parser.add_argument("--excludes", default=None, help="Exclude filter for instrumentation (default: java.*)")
    parser.add_argument("--report-includes", default=None, help="Include filter for faultLocalizationReport (default: *)")
    parser.add_argument(
        "--run-args",
        default=None,
        help="Extra args for runTestMethods (e.g. \"--junit4 --parallel 4\").",
    )
    return parser.parse_args()


def _env_copy() -> dict[str, str]:
    return os.environ.copy()


def _split_args(raw: str | None) -> list[str]:
    return shlex.split(raw) if raw else []


def run_gzoltar(
    project: str,
    bug_id: str,
    *,
    gzoltar_home: Path | None = None,
    includes: str | None = None,
    excludes: str | None = None,
    report_includes: str | None = None,
    run_args: str | None = None,
) -> Path:
    env = _env_copy()

    workdir = ROOT_DIR / "data" / "raw" / project / f"{bug_id}f"
    if not workdir.is_dir():
        raise FileNotFoundError(f"Fixed version directory not found: {workdir}")

    home = gzoltar_home or Path(os.environ.get("GZOLTAR_HOME", ROOT_DIR / "tools" / "gzoltar"))
    cli_jar = (home / "gzoltarcli.jar").resolve()
    agent_jar = (home / "gzoltaragent.jar").resolve()
    if not cli_jar.is_file() or not agent_jar.is_file():
        raise FileNotFoundError(f"GZoltar jars not found in {home}; expected gzoltarcli.jar and gzoltaragent.jar")

    includes = includes or os.environ.get("GZOLTAR_INCLUDES", "*")
    excludes = excludes or os.environ.get("GZOLTAR_EXCLUDES", "java.*")
    report_includes = report_includes or os.environ.get("GZOLTAR_REPORT_INCLUDES", "*")
    run_args_list = _split_args(run_args or os.environ.get("GZOLTAR_RUN_ARGS"))

    run_cmd(["defects4j", "compile"], cwd=workdir, env=env)

    src_test_dir = defects4j_export(workdir, "dir.src.tests", env=env)
    classes_dir = (workdir / defects4j_export(workdir, "dir.bin.classes", env=env)).resolve()
    test_classes_dir = (workdir / defects4j_export(workdir, "dir.bin.tests", env=env)).resolve()
    if not classes_dir.is_dir():
        raise FileNotFoundError(f"Compiled classes directory not found: {classes_dir}")
    if not test_classes_dir.is_dir():
        raise FileNotFoundError(f"Compiled test classes directory not found: {test_classes_dir}")
    cp_test = defects4j_export(workdir, "cp.test", env=env)

    output_dir = ensure_dir(ROOT_DIR / "data" / "raw" / project / bug_id / "coverage")
    context = output_dir / "context.txt"
    context.write_text(
        "\n".join(
            [
                f"project={project}",
                f"bug_id={bug_id}",
                f"src_test_dir={src_test_dir}",
                f"classes_dir={classes_dir}",
                f"test_classes_dir={test_classes_dir}",
                f"cp_test={cp_test}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    test_list = output_dir / "tests.txt"
    list_cp = join_classpath([cli_jar, test_classes_dir, cp_test])
    run_cmd(
        [
            "java",
            "-cp",
            list_cp,
            "com.gzoltar.cli.Main",
            "listTestMethods",
            str(test_classes_dir),
            "--outputFile",
            str(test_list),
        ],
        cwd=workdir,
        env=env,
    )

    ser_dest = output_dir / "gzoltar.ser"
    if ser_dest.exists():
        ser_dest.unlink()

    agent_opts = ",".join(
        [
            f"destfile={ser_dest}",
            f"buildlocation={classes_dir}",
            f"includes={includes}",
            f"excludes={excludes}",
            "granularity=method",
            "inclnolocationclasses=false",
        ]
    )
    run_cp = join_classpath([cli_jar, classes_dir, test_classes_dir, cp_test])
    run_cmd(
        [
            "java",
            f"-javaagent:{agent_jar}={agent_opts}",
            "-cp",
            run_cp,
            "com.gzoltar.cli.Main",
            "runTestMethods",
            "--collectCoverage",
            *run_args_list,
            "--testMethods",
            str(test_list),
        ],
        cwd=workdir,
        env=env,
    )

    if not ser_dest.is_file():
        raise RuntimeError(f"gzoltar.ser not produced at {ser_dest}")

    report_dir = output_dir / "report"
    report_build_location = output_dir / "build_location"
    if not report_build_location.is_dir():
        report_build_location.mkdir(parents=True, exist_ok=True)
        shutil.copytree(classes_dir, report_build_location, dirs_exist_ok=True)
        shutil.copytree(test_classes_dir, report_build_location, dirs_exist_ok=True)
    run_cmd(
        [
            "java",
            "-jar",
            str(cli_jar),
            "faultLocalizationReport",
            "--dataFile",
            str(ser_dest),
            "--buildLocation",
            str(report_build_location),
            "--outputDirectory",
            str(report_dir),
            "--granularity",
            "method",
            "--formula",
            "OCHIAI",
            "--formatter",
            "TXT",
            "--includes",
            report_includes,
        ],
        cwd=workdir,
        env=env,
    )

    matrix_dir = report_dir / "sfl" / "txt"
    spectra_csv = matrix_dir / "spectra.csv"
    tests_csv = matrix_dir / "tests.csv"
    matrix_txt = matrix_dir / "matrix.txt"
    matrix_out = output_dir / "matrix.csv"

    run_cmd(
        [
            sys.executable,
            str(ROOT_DIR / "scripts" / "parse_gzoltar_matrix.py"),
            str(spectra_csv),
            str(tests_csv),
            str(matrix_txt),
            str(matrix_out),
        ],
        cwd=ROOT_DIR,
        env=env,
    )

    print(f"[done] GZoltar coverage saved to {output_dir}")
    return output_dir


def main() -> None:
    args = parse_args()
    run_gzoltar(
        args.project,
        args.bug_id,
        gzoltar_home=Path(args.gzoltar_home).resolve() if args.gzoltar_home else None,
        includes=args.includes,
        excludes=args.excludes,
        report_includes=args.report_includes,
        run_args=args.run_args,
    )


if __name__ == "__main__":
    main()

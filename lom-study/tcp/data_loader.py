from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Set, Tuple


@dataclass
class CoverageMatrix:
    tests: List[str]
    methods: List[str]
    hits: List[List[int]]


@dataclass
class ImpactProbabilities:
    methods: Dict[str, float]


def read_coverage_matrix(path: Path) -> CoverageMatrix:
    with path.open(encoding="utf-8") as fh:
        reader = csv.reader(fh)
        header = next(reader)
        methods = header[1:]
        tests = []
        hits: List[List[int]] = []
        for row in reader:
            tests.append(row[0])
            hits.append([int(value) for value in row[1:]])
    return CoverageMatrix(tests=tests, methods=methods, hits=hits)


def read_impact_probabilities(path: Path) -> ImpactProbabilities:
    methods: Dict[str, float] = {}
    with path.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            key = impact_signature(row["owner_internal"], row["method"], row["descriptor"])
            methods[key] = float(row["impact_probability"])
    return ImpactProbabilities(methods=methods)


def impact_signature(owner_internal: str, method: str, descriptor: str) -> str:
    params = descriptor_to_params(descriptor)
    owner = owner_internal.replace("/", ".")
    return f"{owner}.{method}({','.join(params)})"


def coverage_signature(raw_method: str) -> str:
    value = raw_method.strip().strip('"')
    method_part = value.split(":", 1)[0]
    if "#" in method_part:
        class_part, method_data = method_part.split("#", 1)
    else:
        class_part, method_data = method_part, ""

    owner = normalize_class_name(class_part)

    if "(" in method_data:
        method_name, params_part = method_data.split("(", 1)
        params_part = params_part.rstrip(")")
        params = [] if not params_part else [param.strip() for param in params_part.split(",")]
    else:
        method_name = method_data
        params = []

    return f"{owner}.{method_name}({','.join(params)})"


def descriptor_to_params(descriptor: str) -> Tuple[str, ...]:
    assert descriptor.startswith("("), descriptor
    params = []
    i = 1
    while i < len(descriptor) and descriptor[i] != ")":
        param, i = _parse_type(descriptor, i)
        params.append(param)
    return tuple(params)


def _parse_type(descriptor: str, index: int) -> Tuple[str, int]:
    array_dim = 0
    while descriptor[index] == "[":
        array_dim += 1
        index += 1
    code = descriptor[index]
    index += 1
    if code == "L":
        end = descriptor.index(";", index)
        type_name = descriptor[index:end].replace("/", ".")
        index = end + 1
    else:
        type_name = PRIMITIVE_TYPES[code]
    if array_dim:
        type_name = type_name + "[]" * array_dim
    return type_name, index


PRIMITIVE_TYPES = {
    "Z": "boolean",
    "B": "byte",
    "C": "char",
    "S": "short",
    "I": "int",
    "J": "long",
    "F": "float",
    "D": "double",
    "V": "void",
}


def normalize_class_name(raw_class: str) -> str:
    raw = raw_class.strip()
    tokens = raw.split("$")
    if not tokens:
        return raw

    base = tokens[0]
    components = []
    literal_next = False
    for token in tokens[1:]:
        if token == "":
            literal_next = True
            continue
        if literal_next:
            components.append(f"${token}")
            literal_next = False
        else:
            components.append(token)

    owner = base
    if components:
        first = components[0]
        if first.startswith("$"):
            owner += f".{first}"
        else:
            owner += f".{first}"
        for comp in components[1:]:
            if comp.startswith("$"):
                owner += comp
            else:
                owner += f"${comp}"
    return owner


def parse_callgraph(path: Path) -> List[Tuple[str, str]]:
    """
    Разбор callgraph.txt, сгенерированного java-callgraph.
    Возвращает список рёбер (caller_sig, callee_sig) в строковом представлении.
    """
    edges: List[Tuple[str, str]] = []
    if not path.exists():
        raise FileNotFoundError(f"callgraph.txt not found: {path}")
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or not line.startswith("M:"):
                continue
            try:
                caller_part, callee_part = line[2:].split(") ", 1)
                caller_sig = (caller_part + ")").strip()
                _, callee_sig = callee_part.split(")", 1)
                callee_sig = callee_sig.strip()
            except ValueError:
                continue
            edges.append((caller_sig, callee_sig))
    return edges


def callgraph_signature_to_method(sig: str) -> Tuple[str, str, Tuple[str, ...]]:
    """
    Нормализует сигнатуру из callgraph в вид (owner, method, params).
    Формат входа: org.example.Foo: void bar(int, java.lang.String)
    """
    sig = sig.strip()
    if ": " not in sig:
        return ("", "", tuple())
    owner_part, rest = sig.split(": ", 1)
    owner = owner_part.strip()
    if "(" in rest:
        method_part, params_part = rest.split("(", 1)
        params_part = params_part.rsplit(")", 1)[0]
        params = [] if not params_part else [p.strip().replace("...", "[]") for p in params_part.split(",")]
    else:
        method_part = rest.strip()
        params = []
    method = method_part.split()[-1] if " " in method_part else method_part
    return (owner.replace("/", "."), method, tuple(params))

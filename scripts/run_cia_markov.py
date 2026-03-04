#!/usr/bin/env python3
"""Расчёт impact_probabilities по данным CIA.

Вход: roc.csv, forward_slicing.csv, callgraph.txt
Выход: impact_probabilities.csv c итоговыми вероятностями методов.
"""

from __future__ import annotations

import argparse
import csv
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Формирование impact_probabilities.csv")
    parser.add_argument("--project", required=True, help="Имя проекта (каталог в data/raw)")
    parser.add_argument("--bug", required=True, help="ID бага (например, 93)")
    parser.add_argument("--max-iter", type=int, default=40, help="Максимальное число итераций марковской модели")
    parser.add_argument("--epsilon", type=float, default=1e-6, help="Допуск для сходимости (L1-норма)")
    parser.add_argument("--min-edge-weight", type=float, default=1e-6, help="Минимальный вес ребра при нормализации")
    return parser.parse_args()


def read_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Не найден файл: {path}")
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        return list(reader)


def descriptor_to_params(descriptor: str) -> Tuple[str, ...]:
    assert descriptor.startswith("("), descriptor
    params = []
    i = 1
    while i < len(descriptor) and descriptor[i] != ")":
        t, i = parse_descriptor_type(descriptor, i)
        params.append(t)
    return tuple(params)


def parse_descriptor_type(descriptor: str, start: int) -> Tuple[str, int]:
    array_dim = 0
    while descriptor[start] == '[':
        array_dim += 1
        start += 1
    code = descriptor[start]
    start += 1
    if code == 'L':
        end = descriptor.index(';', start)
        class_name = descriptor[start:end].replace('/', '.')
        start = end + 1
        base = class_name
    else:
        base = {
            'Z': 'boolean',
            'B': 'byte',
            'C': 'char',
            'S': 'short',
            'I': 'int',
            'J': 'long',
            'F': 'float',
            'D': 'double',
        }[code]
    if array_dim:
        base = base + '[]' * array_dim
    return base, start


def params_to_key(params: Iterable[str]) -> str:
    return ','.join(p.replace(' ', '') for p in params)


def callgraph_parse_signature(sig: str) -> Tuple[str, str, Tuple[str, ...]]:
    class_part, rest = sig.split(':', 1)
    method_name, params_part = rest.split('(', 1)
    params_part = params_part.rstrip(')')
    params = () if not params_part else tuple(p.strip() for p in params_part.split(','))
    return class_part, method_name, params


def load_methods(roc_rows: List[Dict[str, str]], forward_rows: List[Dict[str, str]]):
    methods = {}

    for row in roc_rows:
        owner = row['owner_internal']
        method = row['method']
        descriptor = row['descriptor']
        params = descriptor_to_params(descriptor)
        key = (owner.replace('/', '.'), method, params)
        methods[key] = {
            'owner_internal': owner,
            'method': method,
            'descriptor': descriptor,
            'roc': float(row.get('roc', '0') or 0.0),
            'forward_prob': 0.0,
        }

    for row in forward_rows:
        owner = row['owner_internal']
        method = row['method']
        descriptor = row['descriptor']
        params = descriptor_to_params(descriptor)
        key = (owner.replace('/', '.'), method, params)
        entry = methods.get(key)
        if entry:
            entry['forward_prob'] = float(row.get('probability', '0') or 0.0)
        else:
            methods[key] = {
                'owner_internal': owner,
                'method': method,
                'descriptor': descriptor,
                'roc': 0.0,
                'forward_prob': float(row.get('probability', '0') or 0.0),
            }

    return methods


def parse_callgraph_edges(path: Path, methods_map) -> List[Tuple[Tuple[str, str, Tuple[str, ...]], Tuple[str, str, Tuple[str, ...]]]]:
    edges = []
    if not path.exists():
        raise FileNotFoundError(f"Не найден callgraph.txt: {path}")
    with path.open(encoding='utf-8') as fh:
        for line in fh:
            line = line.strip()
            if not line or not line.startswith('M:'):
                continue
            try:
                caller_part, callee_part = line[2:].split(') ', 1)
            except ValueError:
                continue
            caller_sig = (caller_part + ')').strip()
            _, callee_sig = callee_part.split(')', 1)
            callee_sig = callee_sig.strip()

            caller_key = signature_to_key(caller_sig)
            callee_key = signature_to_key(callee_sig)

            if caller_key in methods_map and callee_key in methods_map:
                edges.append((caller_key, callee_key))
    return edges


def signature_to_key(sig: str) -> Tuple[str, str, Tuple[str, ...]]:
    class_name, method_name, params = callgraph_parse_signature(sig)
    params = tuple(p for p in params if p)
    normalized_params = []
    for p in params:
        norm = p.replace(' ', '')
        if norm.endswith('...'):
            norm = norm[:-3] + '[]'
        normalized_params.append(norm)
    return (class_name, method_name, tuple(normalized_params))


def build_adjacency(methods, edges, min_edge_weight):
    method_keys = list(methods.keys())
    index = {key: idx for idx, key in enumerate(method_keys)}
    adjacency: List[Dict[int, float]] = [defaultdict(float) for _ in method_keys]

    for caller, callee in edges:
        i = index[caller]
        j = index[callee]
        weight = methods[callee]['forward_prob'] or min_edge_weight
        adjacency[i][j] += weight

    # нормализация
    normalized = []
    for i, row in enumerate(adjacency):
        if row:
            total = sum(row.values())
            if total <= 0:
                normalized.append({i: 1.0})
            else:
                normalized.append({j: w / total for j, w in row.items()})
        else:
            normalized.append({i: 1.0})
    return method_keys, index, normalized


def build_initial_vector(method_keys, methods):
    vector = [methods[key]['roc'] for key in method_keys]
    total = sum(vector)
    if total <= 0:
        return [1.0 / len(vector) for _ in vector]
    return [v / total for v in vector]


def iterate_markov(vector, adjacency, max_iter, epsilon):
    n = len(vector)
    current = list(vector)
    for _ in range(max_iter):
        new_vec = [0.0] * n
        for i, row in enumerate(adjacency):
            for j, w in row.items():
                new_vec[j] += current[i] * w
        total = sum(new_vec)
        if total > 0:
            new_vec = [v / total for v in new_vec]
        diff = sum(abs(new_vec[i] - current[i]) for i in range(n))
        current = new_vec
        if diff < epsilon:
            break
    return current


def write_output(path: Path, method_keys, methods, impact_vector):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='', encoding='utf-8') as fh:
        writer = csv.writer(fh)
        writer.writerow([
            'owner_internal', 'method', 'descriptor',
            'roc', 'forward_probability', 'impact_probability'
        ])
        for key, impact in sorted(zip(method_keys, impact_vector), key=lambda x: (x[0][0], x[0][1], x[0][2])):
            entry = methods[key]
            writer.writerow([
                entry['owner_internal'],
                entry['method'],
                entry['descriptor'],
                f"{entry['roc']:.6f}",
                f"{entry['forward_prob']:.6f}",
                f"{impact:.6f}",
            ])


def main() -> None:
    args = parse_args()
    root = Path(__file__).resolve().parents[1]
    base = root / 'data' / 'raw' / args.project / str(args.bug) / 'cia'

    roc_rows = read_csv(base / 'roc.csv')
    forward_rows = read_csv(base / 'forward_slicing.csv')
    methods = load_methods(roc_rows, forward_rows)

    edges = parse_callgraph_edges(base / 'callgraph.txt', methods)
    if not edges:
        print('[warn] Не удалось сопоставить рёбра call graph с методами', file=sys.stderr)

    method_keys, _, adjacency = build_adjacency(methods, edges, args.min_edge_weight)
    initial = build_initial_vector(method_keys, methods)
    impact = iterate_markov(initial, adjacency, args.max_iter, args.epsilon)

    write_output(base / 'impact_probabilities.csv', method_keys, methods, impact)
    print(f"[done] impact_probabilities.csv создано ({base / 'impact_probabilities.csv'})")


if __name__ == '__main__':
    main()

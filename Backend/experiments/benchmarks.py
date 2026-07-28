"""Unified access to the benchmarks, with the label kept out of reach of predictors.

Two benchmarks are registered:

``uci_audit_v1``
    776 real firms examined by a government external-audit office. Labels are the real
    post-audit findings. Built by ``scripts/build_uci_audit_benchmark.py``.

``gl_synthetic_v1``
    A generated general-ledger corpus used for control conditions the real data cannot
    express (explicit duplicate pairs, segregation-of-duty violations, document gaps).
    Its labels are generator ground truth, not confirmed fraud, and are reported
    separately from the real-label results.

The central guarantee of this module is :func:`BenchmarkCase.model_view`: it returns the
fields a predictor is allowed to see, and it is the only path the runners use. Label,
category, difficulty and split never appear in that view.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATASETS = ROOT / "datasets"

#: Fields removed before any row reaches a predictor.
LABEL_FIELDS = frozenset({
    "risk_label", "risk_category", "difficulty", "split", "label_source",
    "dataset_version", "generator_version", "source_row_index",
})


@dataclass(frozen=True)
class BenchmarkCase:
    case_id: str
    label: int
    category: str
    difficulty: str
    split: str
    fields: dict[str, str]
    evidence_ids: tuple[str, ...] = ()

    def model_view(self) -> dict[str, str]:
        """Exactly what a predictor may see. Excludes the label by construction."""
        return {key: value for key, value in self.fields.items() if key not in LABEL_FIELDS}

    def evidence(self, corpus: dict[str, str]) -> dict[str, str]:
        return {key: corpus[key] for key in self.evidence_ids if key in corpus}


@dataclass(frozen=True)
class Benchmark:
    name: str
    label_kind: str
    description: str
    cases: tuple[BenchmarkCase, ...]
    corpus: dict[str, str] = field(default_factory=dict)
    manifest: dict = field(default_factory=dict)

    def split(self, split: str) -> tuple[BenchmarkCase, ...]:
        return tuple(case for case in self.cases if case.split == split)

    @property
    def evaluation(self) -> tuple[BenchmarkCase, ...]:
        return self.split("evaluation")

    @property
    def development(self) -> tuple[BenchmarkCase, ...]:
        return self.split("development")

    def evaluation_ids(self) -> set[str]:
        return {case.case_id for case in self.evaluation}

    def labels(self, cases: tuple[BenchmarkCase, ...] | None = None) -> dict[str, int]:
        return {case.case_id: case.label for case in (cases or self.evaluation)}


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _load_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(
            f"benchmark file {path} is missing; run the corresponding build script first"
        )
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"benchmark file {path} contains no rows")
    return rows


def _build(name: str, label_kind: str, description: str, csv_path: Path,
           manifest_path: Path, corpus_path: Path | None,
           id_column: str, evidence_column: str) -> Benchmark:
    rows = _load_csv(csv_path)
    seen: set[str] = set()
    cases: list[BenchmarkCase] = []
    for row in rows:
        case_id = row[id_column].strip()
        if not case_id:
            raise ValueError(f"{csv_path.name}: blank {id_column}")
        if case_id in seen:
            raise ValueError(f"{csv_path.name}: duplicate case id {case_id}")
        seen.add(case_id)
        label = int(row["risk_label"])
        if label not in (0, 1):
            raise ValueError(f"{case_id}: risk_label must be 0 or 1")
        split = row["split"].strip()
        if split not in {"development", "evaluation"}:
            raise ValueError(f"{case_id}: unknown split {split!r}")
        evidence = tuple(part for part in row.get(evidence_column, "").split(";") if part)
        cases.append(BenchmarkCase(
            case_id=case_id, label=label, category=row.get("risk_category", "unknown"),
            difficulty=row.get("difficulty", "unknown"), split=split,
            fields=dict(row), evidence_ids=evidence,
        ))

    corpus: dict[str, str] = {}
    if corpus_path is not None and corpus_path.exists():
        corpus = _load_json(corpus_path).get("documents", {})

    return Benchmark(name=name, label_kind=label_kind, description=description,
                     cases=tuple(cases), corpus=corpus,
                     manifest=_load_json(manifest_path))


def load_uci_audit() -> Benchmark:
    return _build(
        name="uci_audit_v1",
        label_kind="real",
        description=("776 firms examined by a government external-audit office; labels are the "
                     "real post-audit fraud-risk findings (UCI dataset 475)."),
        csv_path=DATASETS / "uci_audit_v1.csv",
        manifest_path=DATASETS / "uci_audit_v1.manifest.json",
        corpus_path=DATASETS / "uci_audit_v1.evidence.json",
        id_column="transaction_id", evidence_column="evidence_ids",
    )


def load_gl_synthetic() -> Benchmark:
    return _build(
        name="gl_synthetic_v1",
        label_kind="synthetic",
        description=("Generated general-ledger corpus covering control conditions absent from "
                     "the real data; labels are generator ground truth, not confirmed fraud."),
        csv_path=DATASETS / "gl_guardian_benchmark_v1.csv",
        manifest_path=DATASETS / "gl_guardian_benchmark_v1.manifest.json",
        corpus_path=DATASETS / "gl_guardian_benchmark_v1.evidence.json",
        id_column="transaction_id", evidence_column="evidence_ids",
    )


REGISTRY = {
    "uci_audit_v1": load_uci_audit,
    "gl_synthetic_v1": load_gl_synthetic,
}


def load(name: str) -> Benchmark:
    if name not in REGISTRY:
        raise KeyError(f"unknown benchmark {name!r}; available: {sorted(REGISTRY)}")
    return REGISTRY[name]()

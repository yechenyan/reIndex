from __future__ import annotations

import json
import math
import statistics
import time
from dataclasses import dataclass
from pathlib import Path

from reindex_server.domain import SearchOptions
from reindex_server.service import ReindexService


@dataclass(frozen=True)
class EvaluationCase:
    query: str
    relevant_node_ids: frozenset[str]
    relevant_unit_ids: frozenset[str]

    @property
    def relevant_count(self) -> int:
        return len(self.relevant_node_ids) + len(self.relevant_unit_ids)


def load_dataset(path: Path) -> list[EvaluationCase]:
    cases: list[EvaluationCase] = []
    for line_number, line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), 1
    ):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
            case = EvaluationCase(
                query=value["query"],
                relevant_node_ids=frozenset(value.get("relevant_node_ids", [])),
                relevant_unit_ids=frozenset(value.get("relevant_unit_ids", [])),
            )
        except (KeyError, TypeError, json.JSONDecodeError) as error:
            raise ValueError(
                f"invalid evaluation case on line {line_number}"
            ) from error
        if not case.query.strip() or case.relevant_count == 0:
            raise ValueError(
                f"evaluation case on line {line_number} needs a query and relevance IDs"
            )
        cases.append(case)
    if not cases:
        raise ValueError("evaluation dataset is empty")
    return cases


def evaluate(
    service: ReindexService,
    collection_id: str,
    cases: list[EvaluationCase],
    mode: str,
    *,
    cutoffs: tuple[int, ...] = (5, 10),
    candidate_limit: int = 100,
    lexical_weight: float = 0.5,
    semantic_weight: float = 1.0,
    rrf_k: int = 60,
) -> dict:
    maximum = max(cutoffs)
    totals = {cutoff: {"recall": 0.0, "mrr": 0.0, "ndcg": 0.0} for cutoff in cutoffs}
    latencies: list[float] = []
    warmup_ms = 0.0
    if mode in {"semantic", "hybrid"}:
        started = time.perf_counter()
        service.embeddings.embed_query(cases[0].query)
        warmup_ms = (time.perf_counter() - started) * 1000
    for case in cases:
        started = time.perf_counter()
        response = service.search(
            collection_id,
            SearchOptions(
                case.query,
                mode,
                maximum,
                candidate_limit,
                lexical_weight=lexical_weight,
                semantic_weight=semantic_weight,
                rrf_k=rrf_k,
            ),
        )
        latencies.append((time.perf_counter() - started) * 1000)
        gains = _relevance_gains(case, response.results)
        for cutoff in cutoffs:
            metrics = _metrics(gains[:cutoff], case.relevant_count)
            for name, value in metrics.items():
                totals[cutoff][name] += value
    count = len(cases)
    return {
        "mode": mode,
        "queries": count,
        "candidate_limit": candidate_limit,
        "ranking": {
            "lexical_weight": lexical_weight,
            "semantic_weight": semantic_weight,
            "rrf_k": rrf_k,
        },
        "metrics": {
            f"@{cutoff}": {
                name: round(value / count, 6) for name, value in totals[cutoff].items()
            }
            for cutoff in cutoffs
        },
        "latency_ms": {
            "model_warmup": round(warmup_ms, 3),
            "mean": round(statistics.fmean(latencies), 3),
            "p50": round(_percentile(latencies, 0.50), 3),
            "p95": round(_percentile(latencies, 0.95), 3),
        },
    }


def _relevance_gains(case: EvaluationCase, hits) -> list[int]:
    matched_nodes: set[str] = set()
    matched_units: set[str] = set()
    gains: list[int] = []
    for hit in hits:
        node_id, unit_id = hit.unit.node_id, hit.unit.id
        relevant = False
        if node_id in case.relevant_node_ids and node_id not in matched_nodes:
            matched_nodes.add(node_id)
            relevant = True
        if unit_id in case.relevant_unit_ids and unit_id not in matched_units:
            matched_units.add(unit_id)
            relevant = True
        gains.append(int(relevant))
    return gains


def _metrics(gains: list[int], relevant_count: int) -> dict[str, float]:
    matched = sum(gains)
    first = next((rank for rank, gain in enumerate(gains, 1) if gain), None)
    dcg = sum(gain / math.log2(rank + 1) for rank, gain in enumerate(gains, 1))
    ideal = min(relevant_count, len(gains))
    idcg = sum(1 / math.log2(rank + 1) for rank in range(1, ideal + 1))
    return {
        "recall": matched / relevant_count,
        "mrr": 1 / first if first else 0.0,
        "ndcg": dcg / idcg if idcg else 0.0,
    }


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = max(0, math.ceil(len(ordered) * fraction) - 1)
    return ordered[index]

"""Check preserved artifacts, exact certificates, trace replay and tiny oracle."""

import argparse
import csv
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from flowlab import from_dict, verify
from scripts.run_study import oracle, source_hashes


def replay(network, result: dict) -> None:
    arcs = {arc.id: arc for arc in network.arcs}
    flow = dict.fromkeys(arcs, 0)
    delivered = cost = 0
    counts = {"AUGMENT": 0, "CANCEL_CYCLE": 0}
    for number, event in enumerate(result["trace"], 1):
        assert event["step"] == number
        assert type(event["amount"]) is int and event["amount"] > 0
        edges = event["edges"]
        assert edges
        assert all(
            first["head"] == second["tail"] for first, second in zip(edges, edges[1:])
        )
        if event["kind"] == "AUGMENT":
            assert (
                edges[0]["tail"] == network.source and edges[-1]["head"] == network.sink
            )
            delivered += event["amount"]
        else:
            assert event["kind"] == "CANCEL_CYCLE"
            assert edges[0]["tail"] == edges[-1]["head"]
            assert event["unit_cost"] < 0
        counts[event["kind"]] += 1
        unit_cost = 0
        for edge in edges:
            arc = arcs[edge["arc"]]
            direction = edge["direction"]
            assert direction in (-1, 1)
            expected_ends = (
                (arc.tail, arc.head) if direction == 1 else (arc.head, arc.tail)
            )
            assert (edge["tail"], edge["head"]) == expected_ends
            capacity = arc.capacity - flow[arc.id] if direction == 1 else flow[arc.id]
            assert capacity == edge["residual_capacity"] and capacity >= event["amount"]
            assert edge["cost"] == direction * arc.cost
            flow[arc.id] += direction * event["amount"]
            unit_cost += direction * arc.cost
        assert event["unit_cost"] == unit_cost
        cost += unit_cost * event["amount"]
        assert event["cost_delta"] == unit_cost * event["amount"]
        assert event["objective"] == cost and event["delivered"] == delivered
    assert (
        result["flow"] == flow
        and result["objective"] == cost
        and result["delivered"] == delivered
    )
    assert result["counts"]["augmentations"] == counts["AUGMENT"]
    assert result["counts"]["cancellations"] == counts["CANCEL_CYCLE"]


def verify_artifacts(out: Path) -> None:
    provenance = json.loads((out / "results/provenance.json").read_text())
    assert (
        source_hashes() == provenance["source_sha256_lf"]
    ), "source provenance changed"
    for name, expected in provenance["artifact_sha256"].items():
        assert hashlib.sha256((out / name).read_bytes()).hexdigest() == expected, name
    summary = json.loads((out / "results/summary.json").read_text())
    by_name = {}
    for row in summary:
        label = row["scenario"]
        network = from_dict(
            json.loads((out / "examples" / f"{label}.json").read_text())
        )
        result = json.loads((out / "results/cases" / f"{label}.json").read_text())
        assert verify(network, result) == result["verification"]
        replay(network, result)
        assert all(
            row[key] == result[key] for key in ("status", "objective", "delivered")
        )
        assert row["required"] == network.required
        assert all(row[key] == result["counts"][key] for key in result["counts"])
        by_name[label] = result
    corpus = json.loads((out / "results/oracle-corpus.json").read_text())
    for row in corpus:
        network = from_dict(row["input"])
        expected, assignments = oracle(network)
        result = row["result"]
        assert (
            row["oracle_objective"] == expected
            and row["assignments_enumerated"] == assignments
        )
        assert result["status"] == ("INFEASIBLE" if expected is None else "OPTIMAL")
        assert expected is None or result["objective"] == expected
        verify(network, result)
        replay(network, result)
    environment = json.loads((out / "results/environment.json").read_text())
    timings = list(
        csv.DictReader((out / "results/timings.csv").open(newline="", encoding="utf-8"))
    )
    samples = environment["timing"]["samples_per_case"]
    assert len(timings) == len(summary) * samples
    for index, row in enumerate(timings, 1):
        assert int(row["ordinal"]) == index and int(row["elapsed_ns"]) > 0
        assert row["status"] == by_name[row["scenario"]]["status"]
        assert int(row["objective"]) == by_name[row["scenario"]]["objective"]
    for label in by_name:
        assert sorted(
            int(row["sample"]) for row in timings if row["scenario"] == label
        ) == list(range(1, samples + 1))
    assert len(corpus) == environment["oracle"]["cases"]
    assert (
        sum(row["assignments_enumerated"] for row in corpus)
        == environment["oracle"]["assignments"]
    )
    print(
        f"Verified {len(summary)} exact cases, {len(corpus)} oracle cases, {len(timings)} timing samples, all traces and artifact/source hashes."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=ROOT)
    verify_artifacts(parser.parse_args().output_dir.resolve())

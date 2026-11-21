"""Reproduce exact results, randomized oracle evidence, and local timing samples."""

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import io
import itertools
import json
from pathlib import Path
import platform
import random
import subprocess
import sys
from time import perf_counter_ns

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from flowlab import Arc, Network, solve, verify
from scripts.fixtures import scenarios


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.replace("\r\n", "\n"), encoding="utf-8", newline="\n")


def write_json(path: Path, value: object) -> None:
    write_text(
        path, json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"
    )


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_hashes() -> dict:
    files = sorted(
        [
            *ROOT.glob("flowlab/*.py"),
            *(
                ROOT / "scripts" / name
                for name in (
                    "fixtures.py",
                    "report.py",
                    "run_study.py",
                    "verify_results.py",
                )
            ),
            *(path for path in ROOT.glob("tests/*.py") if path.name != "test_media.py"),
        ]
    )
    return {
        file.relative_to(ROOT)
        .as_posix(): hashlib.sha256(file.read_bytes().replace(b"\r\n", b"\n"))
        .hexdigest()
        for file in files
    }


def oracle(network: Network) -> tuple[int | None, int]:
    # Exhaustive Cartesian product, independent of residual graph algorithms.
    best = None
    assignments = 0
    for values in itertools.product(*(range(arc.capacity + 1) for arc in network.arcs)):
        assignments += 1
        balances = {node: 0 for node in network.nodes}
        for arc, value in zip(network.arcs, values):
            balances[arc.tail] += value
            balances[arc.head] -= value
        target = {
            node: (
                network.required
                if node == network.source
                else -network.required if node == network.sink else 0
            )
            for node in network.nodes
        }
        if balances == target:
            objective = sum(
                value * arc.cost for arc, value in zip(network.arcs, values)
            )
            best = objective if best is None else min(best, objective)
    return best, assignments


def run(out: Path, samples: int, oracle_cases: int) -> None:
    results = out / "results"
    results.mkdir(parents=True, exist_ok=True)
    tests = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    write_text(results / "test-results.txt", tests.stdout + tests.stderr)
    print(tests.stdout + tests.stderr)
    tests.check_returncode()
    cases = scenarios()
    summary = []
    for label, (network, budget, description) in cases.items():
        result = solve(network, budget)
        result["verification"] = verify(network, result)
        write_json(out / "examples" / f"{label}.json", network.to_dict())
        write_json(results / "cases" / f"{label}.json", result)
        summary.append(
            {
                "scenario": label,
                "description": description,
                "status": result["status"],
                "required": network.required,
                "delivered": result["delivered"],
                "objective": result["objective"],
                **result["counts"],
            }
        )
        for _ in range(3):
            solve(network, budget)

    # Predeclared, seeded interleaving reduces systematic configuration ordering.
    order = [label for _ in range(samples) for label in cases]
    random.Random(51029).shuffle(order)
    timing_rows = []
    occurrence = dict.fromkeys(cases, 0)
    for ordinal, label in enumerate(order, 1):
        network, budget, _ = cases[label]
        start = perf_counter_ns()
        result = solve(network, budget)
        elapsed = perf_counter_ns() - start
        verify(network, result)  # Explicitly outside the timed region.
        occurrence[label] += 1
        timing_rows.append(
            {
                "ordinal": ordinal,
                "scenario": label,
                "sample": occurrence[label],
                "elapsed_ns": elapsed,
                "status": result["status"],
                "objective": result["objective"],
            }
        )
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(
        stream, fieldnames=list(timing_rows[0]), lineterminator="\n"
    )
    writer.writeheader()
    writer.writerows(timing_rows)
    write_text(results / "timings.csv", stream.getvalue())

    rng = random.Random(660274)
    corpus = []
    for index in range(oracle_cases):
        nodes = tuple("s t a b".split()[: rng.randint(2, 4)])
        arcs = []
        for edge in range(rng.randint(0, 7)):
            tail, head = rng.sample(nodes, 2)
            arcs.append(
                Arc(f"e{edge}", tail, head, rng.randint(0, 2), rng.randint(-4, 5))
            )
        network = Network(nodes, tuple(arcs), "s", "t", rng.randint(0, 3))
        expected, assignments = oracle(network)
        result = solve(network)
        verify(network, result)
        assert result["status"] == ("INFEASIBLE" if expected is None else "OPTIMAL")
        assert expected is None or result["objective"] == expected
        corpus.append(
            {
                "case": index,
                "input": network.to_dict(),
                "result": result,
                "oracle_objective": expected,
                "assignments_enumerated": assignments,
            }
        )
    write_json(results / "oracle-corpus.json", corpus)
    write_json(results / "summary.json", summary)
    write_json(
        results / "environment.json",
        {
            "recorded_utc": datetime.now(timezone.utc).isoformat(),
            "python": sys.version,
            "platform": platform.platform(),
            "processor": platform.processor(),
            "timing": {
                "clock": "time.perf_counter_ns",
                "samples_per_case": samples,
                "untimed_warmups_per_case": 3,
                "order_seed": 51029,
                "scope": "solve only; includes trace construction, excludes parsing, serialization and verification",
                "claim": "local micro-duration observations; no production or cross-machine performance claim",
            },
            "oracle": {
                "seed": 660274,
                "cases": oracle_cases,
                "assignments": sum(row["assignments_enumerated"] for row in corpus),
            },
            "command": f"python scripts/run_study.py --samples {samples} --oracle-cases {oracle_cases}",
        },
    )
    from scripts.report import generate

    if out != ROOT:
        for name in ("algorithm.md", "format.md", "methodology.md"):
            write_text(
                out / "docs" / name, (ROOT / "docs" / name).read_text(encoding="utf-8")
            )
    generate(out)
    paths = sorted(
        [
            *out.glob("examples/*.json"),
            *results.glob("**/*"),
            *out.glob("docs/figures/*.svg"),
            out / "docs/report.html",
        ]
    )
    artifacts = {
        path.relative_to(out).as_posix(): sha(path)
        for path in paths
        if path.is_file() and path.name != "provenance.json"
    }
    write_json(
        results / "provenance.json",
        {
            "format": 1,
            "source_sha256_lf": source_hashes(),
            "artifact_sha256": artifacts,
        },
    )
    from scripts.verify_results import verify_artifacts

    verify_artifacts(out)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=ROOT)
    parser.add_argument("--samples", type=int, default=25)
    parser.add_argument("--oracle-cases", type=int, default=120)
    args = parser.parse_args()
    if not 1 <= args.samples <= 100 or not 1 <= args.oracle_cases <= 500:
        parser.error("samples must be 1..100 and oracle-cases 1..500")
    run(args.output_dir.resolve(), args.samples, args.oracle_cases)

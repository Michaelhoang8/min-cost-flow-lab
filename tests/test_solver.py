import copy
import itertools
import json
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

from flowlab import Arc, Network, from_dict, solve, verify
from scripts.fixtures import scenarios


def brute_force(network: Network) -> tuple[int | None, int]:
    """Independent enumeration of every bounded arc-flow assignment."""
    best = None
    feasible = 0
    for values in itertools.product(*(range(arc.capacity + 1) for arc in network.arcs)):
        totals = {node: 0 for node in network.nodes}
        for arc, value in zip(network.arcs, values):
            totals[arc.tail] += value
            totals[arc.head] -= value
        target = {
            node: (
                network.required
                if node == network.source
                else -network.required if node == network.sink else 0
            )
            for node in network.nodes
        }
        if totals != target:
            continue
        feasible += 1
        cost = sum(arc.cost * value for arc, value in zip(network.arcs, values))
        best = cost if best is None else min(best, cost)
    return best, feasible


def check_trace(test: unittest.TestCase, network: Network, result: dict) -> None:
    flows = dict.fromkeys((arc.id for arc in network.arcs), 0)
    arcs = {arc.id: arc for arc in network.arcs}
    objective = delivered = 0
    for index, event in enumerate(result["trace"], 1):
        test.assertEqual(event["step"], index)
        edges = event["edges"]
        test.assertTrue(edges)
        test.assertGreater(event["amount"], 0)
        for first, second in zip(edges, edges[1:]):
            test.assertEqual(first["head"], second["tail"])
        if event["kind"] == "AUGMENT":
            test.assertEqual(edges[0]["tail"], network.source)
            test.assertEqual(edges[-1]["head"], network.sink)
            delivered += event["amount"]
        else:
            test.assertEqual(edges[0]["tail"], edges[-1]["head"])
            test.assertLess(event["unit_cost"], 0)
        cost = 0
        for edge in edges:
            arc = arcs[edge["arc"]]
            direction = edge["direction"]
            test.assertIn(direction, (-1, 1))
            test.assertEqual(
                (edge["tail"], edge["head"]),
                (arc.tail, arc.head) if direction == 1 else (arc.head, arc.tail),
            )
            capacity = arc.capacity - flows[arc.id] if direction == 1 else flows[arc.id]
            test.assertEqual(edge["residual_capacity"], capacity)
            test.assertGreaterEqual(capacity, event["amount"])
            test.assertEqual(edge["cost"], arc.cost * direction)
            flows[arc.id] += event["amount"] * direction
            cost += arc.cost * direction
        test.assertEqual(event["unit_cost"], cost)
        objective += event["amount"] * cost
        test.assertEqual(event["cost_delta"], event["amount"] * cost)
        test.assertEqual(event["objective"], objective)
        test.assertEqual(event["delivered"], delivered)
    test.assertEqual(flows, result["flow"])
    test.assertEqual(objective, result["objective"])
    test.assertEqual(delivered, result["delivered"])


class SolverTests(unittest.TestCase):
    def test_650_seeded_formulas_against_exhaustive_oracle(self):
        rng = random.Random(921673)
        for case in range(650):
            nodes = tuple("s t a b".split()[: rng.randint(2, 4)])
            edges = []
            for i in range(rng.randint(0, 7)):
                tail, head = rng.sample(nodes, 2)
                edges.append(
                    Arc(f"e{i}", tail, head, rng.randint(0, 2), rng.randint(-4, 5))
                )
            network = Network(nodes, tuple(edges), "s", "t", rng.randint(0, 3))
            expected, _ = brute_force(network)
            with self.subTest(case=case):
                result = solve(network)
                verify(network, result)
                check_trace(self, network, result)
                self.assertEqual(
                    result["status"], "INFEASIBLE" if expected is None else "OPTIMAL"
                )
                if expected is not None:
                    self.assertEqual(result["objective"], expected)

    def test_scenarios_and_exact_known_objectives(self):
        expected = {
            "reverse_rerouting": 1,
            "bottleneck": 9,
            "transportation": 20,
            "disconnected_circulation": 0,
            "parallel_arcs": 7,
            "zero_required": -6,
        }
        for label, (network, budget, _) in scenarios().items():
            result = solve(network, budget)
            verify(network, result)
            check_trace(self, network, result)
            if label in expected:
                self.assertEqual(result["objective"], expected[label], label)
        reroute = solve(scenarios()["reverse_rerouting"][0])
        self.assertTrue(
            any(
                edge["direction"] == -1
                for event in reroute["trace"]
                if event["kind"] == "CANCEL_CYCLE"
                for edge in event["edges"]
            )
        )

    def test_budget_boundary_and_optimal_at_zero(self):
        network = scenarios()["reverse_rerouting"][0]
        self.assertEqual(solve(network, 0)["status"], "UNKNOWN")
        self.assertEqual(solve(network, 1)["status"], "OPTIMAL")
        plain = Network(("s", "t"), (Arc("st", "s", "t", 1, 2),), "s", "t", 1)
        self.assertEqual(solve(plain, 0)["status"], "OPTIMAL")
        with self.assertRaises(ValueError):
            solve(plain, True)

    def test_certificate_tampering(self):
        network = scenarios()["reverse_rerouting"][0]
        result = solve(network)
        mutations = [
            lambda x: x["flow"].update(bt=2),
            lambda x: x.update(objective=123),
            lambda x: x["certificate"]["potential"].update(s=999),
            lambda x: x["flow"].update(sa=True),
            lambda x: x.update(delivered=0),
        ]
        for mutate in mutations:
            bad = copy.deepcopy(result)
            mutate(bad)
            with self.assertRaises(ValueError):
                verify(network, bad)
        infeasible = scenarios()["infeasible_cut"][0]
        bad = solve(infeasible)
        bad["certificate"]["source_side"].append("t")
        with self.assertRaises(ValueError):
            verify(infeasible, bad)

    def test_empty_edges_zero_capacity_and_integer_limits(self):
        for required in (0, 1):
            net = Network(("s", "t"), (), "s", "t", required)
            self.assertEqual(
                solve(net)["status"], "OPTIMAL" if required == 0 else "INFEASIBLE"
            )
            verify(net, solve(net))
        net = Network(
            ("s", "t"), (Arc("st", "s", "t", 10_000, -10_000),), "s", "t", 10_000
        )
        self.assertEqual(solve(net)["objective"], -100_000_000)
        verify(net, solve(net))

    def test_validation_and_roundtrip(self):
        data = scenarios()["transportation"][0].to_dict()
        self.assertEqual(from_dict(data).to_dict(), data)
        for mutate in [
            lambda x: x.update(required=True),
            lambda x: x.update(nodes=["s", "s"]),
            lambda x: x["arcs"][0].update(capacity=-1),
            lambda x: x["arcs"][0].update(cost=1.0),
            lambda x: x["arcs"][0].update(head="s"),
            lambda x: x.update(extra=1),
            lambda x: x["arcs"].append(x["arcs"][0]),
        ]:
            bad = copy.deepcopy(data)
            mutate(bad)
            with self.assertRaises(ValueError):
                from_dict(bad)

    def test_serialization_is_defensive_and_malformed_status_is_rejected(self):
        network = scenarios()["reverse_rerouting"][0]
        original = network.arcs[0].capacity
        encoded = network.to_dict()
        encoded["arcs"][0]["capacity"] = -999
        self.assertEqual(network.arcs[0].capacity, original)
        with self.assertRaises(ValueError):
            verify(network, {"status": []})

    def test_cli_exit_codes_and_invalid_input(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "input.json"
            output = Path(folder) / "output.json"
            for label, code in [
                ("reverse_rerouting", 0),
                ("infeasible_cut", 3),
                ("budget_zero", 4),
            ]:
                network, budget, _ = scenarios()[label]
                path.write_text(json.dumps(network.to_dict()), encoding="utf-8")
                run = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "flowlab",
                        str(path),
                        "--cycle-budget",
                        str(budget),
                        "--output",
                        str(output),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                self.assertEqual(run.returncode, code, run.stderr)
                verify_run = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "flowlab",
                        str(path),
                        "--verify",
                        str(output),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                self.assertEqual(verify_run.returncode, 0, verify_run.stderr)
            for malformed in ['{"format":1,"format":1}', '{"format":NaN}', "[]"]:
                path.write_text(malformed, encoding="utf-8")
                run = subprocess.run(
                    [sys.executable, "-m", "flowlab", str(path)],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                self.assertEqual(run.returncode, 2)
                self.assertNotIn("Traceback", run.stderr)


if __name__ == "__main__":
    unittest.main()

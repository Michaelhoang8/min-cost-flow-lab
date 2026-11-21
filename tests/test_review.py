"""Independent closed-form check at the supported node/capacity bounds."""
import unittest

from flowlab import Arc, Network, solve, verify


class ReviewTests(unittest.TestCase):
    def test_full_length_negative_cycle_has_closed_form_optimum(self):
        nodes = tuple(f"n{i}" for i in range(32))
        arcs = tuple(Arc(f"e{i}", nodes[i], nodes[(i + 1) % 32], 10_000, -1)
                     for i in range(32))
        # Conservation forces the first half to carry x+1 and the second x.
        # Capacity gives x<=9999. Every arc has cost -1, so x=9999 is optimal.
        expected = {f"e{i}": 10_000 if i < 16 else 9_999 for i in range(32)}
        for node_order, arc_order in [(nodes, arcs), (nodes[::-1], arcs[::-1])]:
            network = Network(node_order, arc_order, "n0", "n16", 1)
            initial = solve(network, cycle_budget=0)
            self.assertEqual(initial["status"], "UNKNOWN")
            self.assertEqual(initial["objective"], -16)
            self.assertEqual(verify(network, initial)["claim"], "feasible incumbent only")
            result = solve(network, cycle_budget=1)
            self.assertEqual(result["status"], "OPTIMAL")
            self.assertEqual(result["objective"], -319_984)
            self.assertEqual(result["flow"], expected)
            self.assertEqual(result["counts"]["cancellations"], 1)
            self.assertEqual(verify(network, result)["claim"], "optimal")


if __name__ == "__main__":
    unittest.main()

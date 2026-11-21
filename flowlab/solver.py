"""Feasible flow by BFS, then negative residual cycle cancellation.

All disconnected components participate in optimization. Negative-cost
circulations are allowed; this is a flow problem, not a simple-path problem.
"""

from collections import deque
from dataclasses import dataclass

from .model import Network, integer


@dataclass(frozen=True)
class Residual:
    arc: int
    direction: int
    tail: str
    head: str
    capacity: int
    cost: int


def residual(network: Network, flow: list[int]) -> list[Residual]:
    edges = []
    for i, arc in enumerate(network.arcs):
        if flow[i] < arc.capacity:
            edges.append(
                Residual(i, 1, arc.tail, arc.head, arc.capacity - flow[i], arc.cost)
            )
        if flow[i] > 0:
            edges.append(Residual(i, -1, arc.head, arc.tail, flow[i], -arc.cost))
    return edges


def augmenting_path(
    network: Network, edges: list[Residual]
) -> tuple[list[Residual], set[str]]:
    adjacent = {node: [] for node in network.nodes}
    for edge in edges:
        adjacent[edge.tail].append(edge)
    queue = deque([network.source])
    reached = {network.source}
    parent = {}
    while queue:
        tail = queue.popleft()
        for edge in adjacent[tail]:
            if edge.head in reached:
                continue
            reached.add(edge.head)
            parent[edge.head] = edge
            queue.append(edge.head)
    if network.sink not in reached:
        return [], reached
    path = []
    node = network.sink
    while node != network.source:
        edge = parent[node]
        path.append(edge)
        node = edge.tail
    return list(reversed(path)), reached


def negative_cycle(
    network: Network, edges: list[Residual]
) -> tuple[list[Residual], dict[str, int], int]:
    # Zero labels are equivalent to adding a zero-cost super-source to every node.
    distance = {node: 0 for node in network.nodes}
    parent: dict[str, Residual] = {}
    checks = 0
    last = None
    for _ in network.nodes:
        last = None
        for edge in edges:
            checks += 1
            candidate = distance[edge.tail] + edge.cost
            if candidate < distance[edge.head]:
                distance[edge.head] = candidate
                parent[edge.head] = edge
                last = edge.head
        if last is None:
            return [], distance, checks
    # An nth-pass change reaches a negative cycle. Walk n parents to enter it.
    node = last
    for _ in network.nodes:
        node = parent[node].tail
    start = node
    cycle = []
    while True:
        edge = parent[node]
        cycle.append(edge)
        node = edge.tail
        if node == start:
            break
    cycle.reverse()
    if sum(edge.cost for edge in cycle) >= 0:
        raise AssertionError("Bellman-Ford returned a nonnegative cycle")
    return cycle, distance, checks


def solve(network: Network, cycle_budget: int = 10_000) -> dict:
    """Return OPTIMAL, INFEASIBLE, or UNKNOWN with exact flow and trace.

    The budget counts cancellations, not feasibility BFS operations. Exhaustion
    is UNKNOWN only if a further negative cycle actually exists.
    """
    if type(network) is not Network:
        raise ValueError("expected a validated Network")
    integer(cycle_budget, "cycle_budget", 0, 100_000)
    flow = [0] * len(network.arcs)
    delivered = 0
    trace = []
    augmentations = cancellations = checks = 0

    def record(kind: str, path: list[Residual], amount: int) -> None:
        nonlocal delivered
        for edge in path:
            flow[edge.arc] += amount * edge.direction
        if kind == "AUGMENT":
            delivered += amount
        trace.append(
            {
                "step": len(trace) + 1,
                "kind": kind,
                "amount": amount,
                "unit_cost": sum(edge.cost for edge in path),
                "cost_delta": amount * sum(edge.cost for edge in path),
                "delivered": delivered,
                "objective": sum(
                    value * arc.cost for arc, value in zip(network.arcs, flow)
                ),
                "edges": [
                    {
                        "arc": network.arcs[edge.arc].id,
                        "direction": edge.direction,
                        "tail": edge.tail,
                        "head": edge.head,
                        "residual_capacity": edge.capacity,
                        "cost": edge.cost,
                    }
                    for edge in path
                ],
            }
        )

    def result(status: str, certificate: dict) -> dict:
        return {
            "format": 1,
            "status": status,
            "delivered": delivered,
            "objective": sum(
                value * arc.cost for arc, value in zip(network.arcs, flow)
            ),
            "flow": {arc.id: value for arc, value in zip(network.arcs, flow)},
            "certificate": certificate,
            "trace": trace,
            "counts": {
                "augmentations": augmentations,
                "cancellations": cancellations,
                "relaxation_checks": checks,
            },
            "cycle_budget": cycle_budget,
        }

    while delivered < network.required:
        path, reached = augmenting_path(network, residual(network, flow))
        if not path:
            cut = [node for node in network.nodes if node in reached]
            capacity = sum(
                arc.capacity
                for arc in network.arcs
                if arc.tail in reached and arc.head not in reached
            )
            return result(
                "INFEASIBLE", {"kind": "cut", "source_side": cut, "capacity": capacity}
            )
        amount = min(network.required - delivered, min(edge.capacity for edge in path))
        record("AUGMENT", path, amount)
        augmentations += 1

    while True:
        cycle, potential, count = negative_cycle(network, residual(network, flow))
        checks += count
        if not cycle:
            return result("OPTIMAL", {"kind": "potentials", "potential": potential})
        if cancellations == cycle_budget:
            return result(
                "UNKNOWN", {"kind": "budget", "reason": "negative cycle remains"}
            )
        record("CANCEL_CYCLE", cycle, min(edge.capacity for edge in cycle))
        cancellations += 1

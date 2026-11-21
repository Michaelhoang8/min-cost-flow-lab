"""Synthetic, named networks. Arc ordering is intentional and reproducible."""

from flowlab import Arc, Network


def network(nodes: str, rows: list[tuple], required: int) -> Network:
    return Network(
        tuple(nodes.split()), tuple(Arc(*row) for row in rows), "s", "t", required
    )


def scenarios() -> dict[str, tuple[Network, int, str]]:
    reroute = network(
        "s a b t",
        [
            ("sa", "s", "a", 1, 0),
            ("at", "a", "t", 1, 10),
            ("sb", "s", "b", 1, 0),
            ("bt", "b", "t", 1, 1),
        ],
        1,
    )
    bottleneck = network(
        "s a b t",
        [
            ("sa", "s", "a", 3, 1),
            ("sb", "s", "b", 2, 4),
            ("ab", "a", "b", 2, -2),
            ("at", "a", "t", 1, 3),
            ("bt", "b", "t", 3, 1),
        ],
        4,
    )
    transport = network(
        "s W1 W2 W3 D1 D2 D3 t",
        [
            ("sW1", "s", "W1", 4, 0),
            ("sW2", "s", "W2", 3, 0),
            ("sW3", "s", "W3", 3, 0),
            ("W1D1", "W1", "D1", 10, 9),
            ("W1D2", "W1", "D2", 10, 2),
            ("W1D3", "W1", "D3", 10, 5),
            ("W2D1", "W2", "D1", 10, 3),
            ("W2D2", "W2", "D2", 10, 8),
            ("W2D3", "W2", "D3", 10, 4),
            ("W3D1", "W3", "D1", 10, 6),
            ("W3D2", "W3", "D2", 10, 4),
            ("W3D3", "W3", "D3", 10, 1),
            ("D1t", "D1", "t", 3, 0),
            ("D2t", "D2", "t", 4, 0),
            ("D3t", "D3", "t", 3, 0),
        ],
        10,
    )
    disconnected = network(
        "s t x y",
        [
            ("st", "s", "t", 2, 3),
            ("xy", "x", "y", 2, -4),
            ("yx", "y", "x", 2, 1),
        ],
        2,
    )
    parallel = network(
        "s a t",
        [
            ("sa_expensive", "s", "a", 2, 6),
            ("sa_cheap", "s", "a", 2, -1),
            ("as", "a", "s", 1, 2),
            ("at", "a", "t", 3, 1),
        ],
        3,
    )
    return {
        "reverse_rerouting": (
            reroute,
            10_000,
            "One unit moves from the initial expensive path to a cheaper path through reverse residual arcs.",
        ),
        "bottleneck": (
            bottleneck,
            10_000,
            "Four required units saturate the two sink arcs; a negative-cost intermediate arc improves allocation.",
        ),
        "infeasible_cut": (
            Network(bottleneck.nodes, bottleneck.arcs, "s", "t", 5),
            10_000,
            "The requested five units exceed a cut of capacity four.",
        ),
        "transportation": (
            transport,
            10_000,
            "Ten units allocated between three warehouses and three demand nodes, with integer unit costs.",
        ),
        "disconnected_circulation": (
            disconnected,
            10_000,
            "A bounded negative-cost circulation changes the objective outside the source component.",
        ),
        "parallel_arcs": (
            parallel,
            10_000,
            "Parallel and antiparallel original arcs retain separate identities.",
        ),
        "budget_zero": (
            reroute,
            0,
            "A feasible cost-ten incumbent is returned UNKNOWN because a negative cycle remains.",
        ),
        "zero_required": (
            Network(disconnected.nodes, disconnected.arcs, "s", "t", 0),
            10_000,
            "Zero required transfer still permits a beneficial bounded circulation.",
        ),
    }

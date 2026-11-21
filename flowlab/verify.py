"""Independent linear-time certificate checking; no solver helpers are used."""

from .model import Network


def exact_int(value: object) -> bool:
    return type(value) is int


def verify(network: Network, result: dict) -> dict:
    """Raise ValueError for an invalid primal result or certificate.

    UNKNOWN verifies a feasible incumbent only. It certifies neither optimality
    nor the solver's budget bookkeeping. INFEASIBLE verifies a separating cut.
    """
    if (
        not isinstance(result, dict)
        or not isinstance(result.get("status"), str)
        or result.get("status") not in {"OPTIMAL", "INFEASIBLE", "UNKNOWN"}
    ):
        raise ValueError("unknown result status")
    flows = result.get("flow")
    if not isinstance(flows, dict) or set(flows) != {arc.id for arc in network.arcs}:
        raise ValueError("flow must contain exactly the input arc IDs")
    balance = dict.fromkeys(network.nodes, 0)
    objective = 0
    for arc in network.arcs:
        value = flows[arc.id]
        if not exact_int(value) or not 0 <= value <= arc.capacity:
            raise ValueError("invalid flow capacity or type")
        balance[arc.tail] += value
        balance[arc.head] -= value
        objective += value * arc.cost
    delivered = result.get("delivered")
    if not exact_int(delivered) or not 0 <= delivered <= network.required:
        raise ValueError("invalid delivered amount")
    expected = {
        node: (
            delivered
            if node == network.source
            else -delivered if node == network.sink else 0
        )
        for node in network.nodes
    }
    if balance != expected:
        raise ValueError("flow conservation failed")
    if not exact_int(result.get("objective")) or result["objective"] != objective:
        raise ValueError("objective mismatch")
    status = result["status"]
    certificate = result.get("certificate")
    if not isinstance(certificate, dict):
        raise ValueError("missing certificate")
    checked_edges = 0
    minimum_reduced_cost = None
    if status == "INFEASIBLE":
        side = certificate.get("source_side")
        if (
            certificate.get("kind") != "cut"
            or not isinstance(side, list)
            or any(not isinstance(node, str) for node in side)
        ):
            raise ValueError("invalid cut")
        selected = set(side)
        if (
            len(side) != len(selected)
            or not selected <= set(network.nodes)
            or network.source not in selected
            or network.sink in selected
        ):
            raise ValueError("invalid source side")
        capacity = sum(
            arc.capacity
            for arc in network.arcs
            if arc.tail in selected and arc.head not in selected
        )
        if (
            not exact_int(certificate.get("capacity"))
            or certificate["capacity"] != capacity
            or capacity >= network.required
            or delivered != capacity
        ):
            raise ValueError("cut does not certify maximum flow below requirement")
    else:
        if delivered != network.required:
            raise ValueError("incumbent does not meet required flow")
        if status == "OPTIMAL":
            potential = certificate.get("potential")
            if (
                certificate.get("kind") != "potentials"
                or not isinstance(potential, dict)
                or set(potential) != set(network.nodes)
                or any(not exact_int(value) for value in potential.values())
            ):
                raise ValueError("invalid potentials")
            reduced = []
            for arc in network.arcs:
                value = arc.cost + potential[arc.tail] - potential[arc.head]
                if flows[arc.id] < arc.capacity:
                    reduced.append(value)
                if flows[arc.id] > 0:
                    reduced.append(-value)
            if any(value < 0 for value in reduced):
                raise ValueError("negative reduced cost in residual network")
            checked_edges = len(reduced)
            minimum_reduced_cost = min(reduced, default=None)
        elif certificate.get("kind") != "budget":
            raise ValueError("UNKNOWN must carry a budget marker")
    return {
        "valid": True,
        "claim": (
            "optimal"
            if status == "OPTIMAL"
            else "infeasible" if status == "INFEASIBLE" else "feasible incumbent only"
        ),
        "objective": objective,
        "balances": balance,
        "residual_edges_checked": checked_edges,
        "minimum_reduced_cost": minimum_reduced_cost,
    }

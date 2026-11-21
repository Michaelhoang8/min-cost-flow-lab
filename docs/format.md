# Input format and API

```json
{
  "format": 1,
  "nodes": ["s", "a", "t"],
  "source": "s",
  "sink": "t",
  "required": 2,
  "arcs": [
    {"id": "sa", "tail": "s", "head": "a", "capacity": 3, "cost": -1},
    {"id": "at", "tail": "a", "head": "t", "capacity": 2, "cost": 4}
  ]
}
```

The top-level and arc objects accept exactly these fields. Node and arc identifiers are case-sensitive, 1–32 characters, start with an ASCII letter, and then contain ASCII letters, digits, `_` or `-`. Node IDs and arc IDs are each unique. Endpoints must be listed, source and sink distinct, and self-loops are rejected.

Bounds: 2–32 nodes; 0–128 arcs; capacities 0–10,000; cost −10,000–10,000; demand 0–10,000. All numeric model values must be actual integers; booleans and integral-looking floats are rejected. Zero capacities are allowed. JSON duplicate members and nonstandard NaN/Infinity are rejected by the CLI. Input/result files read by the CLI are limited to 256 KB.

Python API:

```python
from flowlab import Arc, Network, solve, verify

network = Network(
    nodes=("s", "t"),
    arcs=(Arc("st", "s", "t", capacity=2, cost=3),),
    source="s",
    sink="t",
    required=2,
)
result = solve(network, cycle_budget=10_000)
checked = verify(network, result)
assert result["objective"] == 6
assert checked["claim"] == "optimal"
```

`Network` validates its tuples on construction; `to_dict()` returns detached serializable dictionaries. `from_dict()` parses the strict model schema. These are ordinary Python objects, not a hostile-code sandbox.

Result fields include `status`, per-original-arc `flow`, `delivered`, `objective`, `certificate`, `trace`, operation `counts`, and `cycle_budget`. Trace steps retain edge identity, direction (`+1` forward, `-1` reverse), actual residual capacity, edge cost, augmentation amount, objective delta and cumulative state.

OPTIMAL carries exact integer node potentials. INFEASIBLE carries the source-side node list and original outgoing cut capacity. UNKNOWN carries a budget marker and a complete feasible flow. Verification raises `ValueError` if the supplied primal values or mathematical certificate are invalid. The verifier checks its mathematical claim, not every decorative/trace field; the artifact replay performs trace checks.

Large budgets can produce a result exceeding the CLI's 256 KB verification-input bound. This bounded lab CLI intentionally requires smaller traces for file-based verification; the in-process verifier has no file-size restriction.

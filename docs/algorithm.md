# Algorithm and correctness

## Primal model

For each directed original arc `e=(u,v)`, choose integer `0 <= f[e] <= capacity[e]`. Net outflow equals the required value at the source, its negative at the sink, and zero elsewhere. Minimize `sum(cost[e] * f[e])`.

The model permits circulations, even in disconnected components. A negative-cost bounded circulation can lower the optimum independently of the source-to-sink transfer. A shortest simple path model would be a different problem.

## Phase 1: feasible flow

Start with all-zero flow. Build residual arcs: forward capacity `capacity-f`, cost `cost`; reverse capacity `f`, cost `-cost`. Breadth-first search discovers a shortest-in-edge-count residual source-to-sink path. Push the smaller of its bottleneck and the remaining demand.

Integral residual capacities give an integral increment of at least one. Demand is at most 10,000, so this phase performs at most 10,000 augmentations. Input ordering determines ties. BFS explores the full reachable set to retain a cut when no path exists.

If the sink is unreachable, the source-reachable residual set defines a cut. Every original arc leaving the cut is saturated; every entering arc has zero flow, otherwise its reverse would leave the reachable set. Thus delivered flow equals the original outgoing cut capacity. If that capacity is below demand, the request is infeasible. The returned partial flow is not cost-optimized.

## Phase 2: cycle cancellation

Run Bellman–Ford with all distances initially zero, equivalent to adding a virtual zero-cost source to every node. This intentionally finds negative cycles in all components.

If the nth relaxation pass changes a label, follow n predecessor edges to enter a cycle, then collect the predecessor cycle and reverse it into forward traversal order. Push its smallest residual capacity. The cycle cost is strictly negative, the objective strictly decreases, and all node balances remain unchanged.

Every objective improvement is an integer of at least one. With finite capacities, the objective has a finite lower bound, so unlimited cycle cancellation terminates. The generic algorithm is pseudopolynomial: a loose bound on cancellations is twice the sum of `capacity * abs(cost)`, with `O(VE)` work per Bellman–Ford detection. This implementation additionally caps cancellations at a caller-selected integer in 0–100,000 (default 10,000).

The budget is checked after detecting a negative cycle. Therefore zero budget can still return OPTIMAL if the feasible flow already has no improving cycle; the exact last permitted cancellation can also return OPTIMAL. A remaining negative cycle after budget exhaustion yields UNKNOWN with a feasible incumbent. This is not a wall-clock timeout.

## Certificate

When Bellman–Ford reaches a pass with no relaxation, its labels satisfy

`p[v] <= p[u] + cost(u,v)`

for every positive-capacity residual arc. Equivalently, `cost + p[u] - p[v] >= 0`. Summing these reduced costs around a cycle cancels all potentials, so no residual cycle has negative original cost.

Any other feasible flow of the same value differs by a feasible residual circulation, decomposable into cycles. With no negative residual cycle, that difference cannot improve cost. Primal feasibility plus the potentials therefore certifies global optimality within this exact model.

`flowlab/verify.py` independently reconstructs balances, objective and residual inequalities from original arcs and returned flow. It does not invoke the solver. The infeasibility verifier checks cut membership, cut capacity below demand, and matching feasible delivered flow. For UNKNOWN it verifies only the feasible incumbent, not budget bookkeeping or optimality.

`scripts/verify_results.py` separately replays each trace from zero flow, checking actual residual capacity, orientation, cycle closure, amount, objective deltas and operation counters.

## References

The implementation follows the classical cycle-cancellation and residual-potential arguments described in [MIT 6.854 minimum-cost flow notes](https://courses.csail.mit.edu/6.854/18/Notes/n9-mincostflow.html). [CMU 15-451/651 Spring 2024 notes, Lecture 13](https://www.cs.cmu.edu/~15451-s24/notes.pdf) present the negative-cycle optimality condition and integral termination argument. These references describe algorithms, not code copied into this repository.

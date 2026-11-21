# Measurement and reproduction

All networks are synthetic. The code and documentation were created with AI assistance. No production system, customer workload, economic impact, or manual development footage is represented.

## Workloads

Eight fixed cases cover reverse-edge rerouting, a saturated bottleneck, an infeasible cut, a three-by-three transportation allocation, a disconnected negative circulation, parallel/antiparallel original arcs, zero budget, and zero required transfer. Each input, complete result and trace is retained.

The 650-network unit-test corpus uses seed 921673. A separate preserved corpus uses seed 660274 and 120 networks by default. Each has 2–4 nodes, 0–7 arcs, capacities 0–2, costs −4–5, and demand 0–3. The oracle enumerates every tuple of original-arc flow values and checks the original balance equations directly. It does not build residual arcs. A tiny-graph oracle is strong evidence within that range, not a proof that arbitrary implementation inputs are correct.

The independent boundary review exercises a 32-node negative-cost ring at capacity 10,000, with one required unit from n0 to n16. Forward and reversed declarations both reach the analytically derived objective −319,984, including the exact budget boundary. Other tests mutate primal values/potentials, serialize defensively, reject invalid model types, and check CLI terminal exits.

## Timings

The study runs three untimed warmups for each case, then 25 observed solve calls per case in a predeclared interleaving shuffled with seed 51029. `time.perf_counter_ns()` measures the solver, including construction of its exact trace. Input parsing, verification, serialization, diagram construction and tests are outside the timing region.

Raw sample order and durations are retained in `results/timings.csv`. The chart shows individual samples, ranges and medians. There is no subtraction of a clock baseline, process isolation, CPU pinning, hardware counter collection, or cross-implementation comparison. Small Python calls are sensitive to scheduler noise, memory allocation, power state and clock overhead; this is local instrumentation, not a throughput benchmark.

The fixed networks' outcomes and certificate checks are deterministic for the same ordered input. Wall-clock durations, UTC recording time and test runtime naturally differ between runs.

## Replay and provenance

```bash
python scripts/verify_results.py
python scripts/run_study.py --output-dir build/reproduction
python scripts/verify_results.py --output-dir build/reproduction
```

The study executes tests first, writes exact input/output evidence, measures real calls, generates the report, hashes its artifacts and runs the independent artifact verifier. The verifier reconstructs the tiny oracle results, replays all trace deltas and checks every primal/certificate claim and artifact digest.

Source hashes use UTF-8 bytes with CRLF normalized to LF. Generated JSON, CSV, HTML, SVG and test logs are written explicitly with LF before hashing. `.gitattributes` preserves this representation in Git and treats screenshots/video as binary. Core, fixture, report, verification and algorithm-test sources are covered; optional capture tooling and its media-integrity test are outside solve provenance. Provenance hashes provide consistency evidence, not cryptographic authorship or an authenticated external timestamp.

The report's diagram geometry is manually laid out, while flow amounts, capacities, costs, residual directions, certificates and timing marks come from saved result data. Report screenshots and recordings, when added, are actual browser captures. A recording documents an automated report review, not a person developing the algorithm.

CI verifies the preserved evidence and runs a fresh smaller study in `build/ci`, leaving committed measurements untouched. Fresh CI observations should agree on exact mathematical results; their durations need not match the original machine.

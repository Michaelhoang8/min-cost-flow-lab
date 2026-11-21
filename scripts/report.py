"""Report and SVG diagrams drawn from actual serialized solver results."""

import csv
import html
import json
import math
from pathlib import Path
import statistics

INK = "#172a32"
BLUE = "#146f97"
RED = "#ad432c"
MUTED = "#6c7d83"
PAPER = "#f8f7f2"


def esc(value) -> str:
    return html.escape(str(value))


def write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value.replace("\r\n", "\n"), encoding="utf-8", newline="\n")


def svg_start(width: int, height: int, title: str) -> list[str]:
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-label="{esc(title)}">',
        f'<rect width="100%" height="100%" fill="{PAPER}"/>',
        '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0 0L10 5L0 10Z" fill="context-stroke"/></marker></defs>',
        "<style>text{font-family:Arial,sans-serif;font-size:15px}.small{font-size:12px}.label{font-size:13px;font-family:monospace}</style>",
    ]


def text(x, y, value, color=INK, anchor="middle", cls="") -> str:
    return f'<text x="{x}" y="{y}" text-anchor="{anchor}" fill="{color}" class="{cls}">{esc(value)}</text>'


def network_svg(
    network: dict, flow: dict, positions: dict, title: str, active_only=False, cut=None
) -> str:
    width, height = 1040, 450
    parts = svg_start(width, height, title)
    if cut:
        parts.append(
            '<rect x="35" y="80" width="585" height="290" fill="#e6eef0" rx="10"/>'
        )
        parts.append(text(55, 105, "SOURCE SIDE OF CUT", MUTED, "start", "small"))
    for arc in network["arcs"]:
        amount = flow[arc["id"]]
        if active_only and not amount:
            continue
        x1, y1 = positions[arc["tail"]]
        x2, y2 = positions[arc["head"]]
        dx, dy = x2 - x1, y2 - y1
        distance = math.hypot(dx, dy)
        ux, uy = dx / distance, dy / distance
        color = (
            RED
            if cut and arc["tail"] in cut and arc["head"] not in cut
            else BLUE if amount else "#aab5b7"
        )
        stroke = 1.4 + min(amount, 4) * 0.65
        parts.append(
            f'<path d="M{x1 + ux * 25:.2f},{y1 + uy * 25:.2f} L{x2 - ux * 29:.2f},{y2 - uy * 29:.2f}" fill="none" stroke="{color}" stroke-width="{stroke}" marker-end="url(#arrow)"/>'
        )
        midx, midy = (x1 + x2) / 2, (y1 + y2) / 2
        label = f'{amount}/{arc["capacity"]} · c {arc["cost"]}'
        parts.append(
            f'<rect x="{midx - 44}" y="{midy - 21}" width="88" height="19" fill="{PAPER}" opacity=".96"/>'
        )
        parts.append(text(midx, midy - 7, label, color, cls="label"))
    for node, (x, y) in positions.items():
        parts.append(f'<circle cx="{x}" cy="{y}" r="24" fill="{INK}"/>')
        parts.append(text(x, y + 5, node, "white"))
    parts.append(
        text(
            32,
            height - 18,
            "Edge label: flow / capacity · c unit cost",
            MUTED,
            "start",
            "small",
        )
    )
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def rerouting_svg(network: dict, result: dict) -> str:
    parts = svg_start(
        1080, 440, "Initial feasible route, negative residual cycle, and final route"
    )
    base = {"s": (45, 150), "a": (150, 70), "b": (150, 230), "t": (255, 150)}
    initial = dict.fromkeys(result["flow"], 0)
    for edge in result["trace"][0]["edges"]:
        initial[edge["arc"]] += result["trace"][0]["amount"] * edge["direction"]
    cycle = next(event for event in result["trace"] if event["kind"] == "CANCEL_CYCLE")
    panels = [
        ("01 / FEASIBLE FLOW", initial, 10),
        ("02 / RESIDUAL CYCLE", None, cycle["unit_cost"]),
        ("03 / OPTIMAL FLOW", result["flow"], result["objective"]),
    ]
    for index, (heading, flow, objective) in enumerate(panels):
        offset = index * 360 + 30
        parts.append(text(offset, 32, heading, MUTED, "start", "small"))
        parts.append(
            text(
                offset,
                365,
                f'{"Cycle cost" if flow is None else "Objective"}: {objective}',
                INK,
                "start",
            )
        )
        edges = (
            cycle["edges"]
            if flow is None
            else [
                {
                    "tail": arc["tail"],
                    "head": arc["head"],
                    "cost": arc["cost"],
                    "direction": 1,
                    "arc": arc["id"],
                }
                for arc in network["arcs"]
            ]
        )
        for edge in edges:
            x1, y1 = base[edge["tail"]]
            x2, y2 = base[edge["head"]]
            x1, x2, y1, y2 = x1 + offset, x2 + offset, y1 + 50, y2 + 50
            distance = math.hypot(x2 - x1, y2 - y1)
            ux, uy = (x2 - x1) / distance, (y2 - y1) / distance
            active = flow is None or flow[edge["arc"]] > 0
            color = RED if edge["direction"] < 0 else BLUE if active else "#c4cdcc"
            dashed = 'stroke-dasharray="6 4"' if edge["direction"] < 0 else ""
            parts.append(
                f'<path d="M{x1 + ux * 20},{y1 + uy * 20} L{x2 - ux * 25},{y2 - uy * 25}" stroke="{color}" stroke-width="{3 if active else 1.4}" fill="none" {dashed} marker-end="url(#arrow)"/>'
            )
            parts.append(
                text(
                    (x1 + x2) / 2,
                    (y1 + y2) / 2 - 7,
                    f'c {edge["cost"]}',
                    color,
                    cls="small",
                )
            )
        for node, (x, y) in base.items():
            parts.append(
                f'<circle cx="{x + offset}" cy="{y + 50}" r="19" fill="{INK}"/>'
            )
            parts.append(text(x + offset, y + 55, node, "white"))
    parts.append(
        text(
            30,
            415,
            "Red dashed arcs undo existing flow. The cancellation preserves the delivered amount of 1.",
            MUTED,
            "start",
            "small",
        )
    )
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def timing_svg(timings: list[dict], labels: list[str]) -> str:
    parts = svg_start(1080, 360, "Actual solve-duration samples, in milliseconds")
    grouped = {
        label: [
            int(row["elapsed_ns"]) / 1e6 for row in timings if row["scenario"] == label
        ]
        for label in labels
    }
    maximum = max(value for values in grouped.values() for value in values) * 1.07
    left, span = 230, 780
    for index in range(5):
        value = maximum * index / 4
        x = left + span * index / 4
        parts.append(f'<path d="M{x} 25V295" stroke="#dce1de"/>')
        parts.append(text(x, 322, f"{value:.3f}", MUTED, cls="small"))
    for index, label in enumerate(labels):
        y = 38 + index * 34
        values = grouped[label]
        parts.append(
            text(left - 16, y + 4, label.replace("_", " "), INK, "end", "small")
        )
        low, high, median = min(values), max(values), statistics.median(values)
        parts.append(
            f'<path d="M{left + low / maximum * span} {y}H{left + high / maximum * span}" stroke="#8cb5c4" stroke-width="2"/>'
        )
        for j, value in enumerate(values):
            parts.append(
                f'<circle cx="{left + value / maximum * span}" cy="{y + (j % 5 - 2) * 2}" r="2.4" fill="{BLUE}" opacity=".5"/>'
            )
        parts.append(
            f'<path d="M{left + median / maximum * span} {y - 8}V{y + 8}" stroke="{RED}" stroke-width="2"/>'
        )
    parts.append(
        text(
            540,
            350,
            "Solve duration (ms) · points: observed calls · red tick: median",
            MUTED,
            cls="small",
        )
    )
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def generate(out: Path) -> None:
    def read(path):
        return json.loads((out / path).read_text(encoding="utf-8"))

    rows = read("results/summary.json")
    env = read("results/environment.json")
    cases = {
        row["scenario"]: read(f'results/cases/{row["scenario"]}.json') for row in rows
    }
    inputs = {row["scenario"]: read(f'examples/{row["scenario"]}.json') for row in rows}
    transport = cases["transportation"]
    positions = {
        "s": (80, 220),
        "W1": (315, 90),
        "W2": (315, 220),
        "W3": (315, 350),
        "D1": (725, 220),
        "D2": (725, 90),
        "D3": (725, 350),
        "t": (960, 220),
    }
    figures = out / "docs/figures"
    write(
        figures / "transportation.svg",
        network_svg(
            inputs["transportation"],
            transport["flow"],
            positions,
            "Optimal transportation allocation; zero-flow arcs omitted",
            True,
        ),
    )
    write(
        figures / "rerouting.svg",
        rerouting_svg(inputs["reverse_rerouting"], cases["reverse_rerouting"]),
    )
    failed = cases["infeasible_cut"]
    write(
        figures / "cut.svg",
        network_svg(
            inputs["infeasible_cut"],
            failed["flow"],
            {"s": (130, 220), "a": (470, 145), "b": (470, 315), "t": (900, 220)},
            "Maximum-flow cut has capacity four",
            cut=set(failed["certificate"]["source_side"]),
        ),
    )
    with (out / "results/timings.csv").open(encoding="utf-8", newline="") as handle:
        timings = list(csv.DictReader(handle))
    write(figures / "timings.svg", timing_svg(timings, list(cases)))
    allocation = ""
    arcs = {arc["id"]: arc for arc in inputs["transportation"]["arcs"]}
    for warehouse in ("W1", "W2", "W3"):
        allocation += f"<tr><th>{warehouse}</th>"
        for demand in ("D1", "D2", "D3"):
            key = warehouse + demand
            amount = transport["flow"][key]
            allocation += f'<td class="{("selected" if amount else "")}"><strong>{amount}</strong><small>unit cost {arcs[key]["cost"]}</small></td>'
        allocation += "</tr>"
    potentials = transport["certificate"]["potential"]
    potential_rows = "".join(
        f'<tr><th>{node}</th><td>{value}</td><td>{transport["verification"]["balances"][node]}</td></tr>'
        for node, value in potentials.items()
    )
    residual_rows = ""
    for arc in inputs["reverse_rerouting"]["arcs"]:
        flow = cases["reverse_rerouting"]["flow"][arc["id"]]
        p = cases["reverse_rerouting"]["certificate"]["potential"]
        for direction, capacity in ((1, arc["capacity"] - flow), (-1, flow)):
            if capacity:
                tail, head = (
                    (arc["tail"], arc["head"])
                    if direction == 1
                    else (arc["head"], arc["tail"])
                )
                reduced = direction * arc["cost"] + p[tail] - p[head]
                residual_rows += f'<tr><td>{tail} → {head}</td><td>{direction * arc["cost"]}</td><td>{p[tail]}</td><td>{p[head]}</td><td>{reduced}</td></tr>'
    result_rows = "".join(
        f'<tr><th>{esc(row["scenario"].replace("_", " "))}</th><td>{row["status"]}</td><td>{row["delivered"]}/{row["required"]}</td><td>{row["objective"]}</td><td>{row["cancellations"]}</td></tr>'
        for row in rows
    )
    html_report = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Min-cost flow · algorithm study</title>
<style>
:root{{--paper:{PAPER};--ink:{INK};--blue:{BLUE};--red:{RED};--muted:{MUTED}}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:16px/1.55 system-ui,sans-serif}}a{{color:var(--blue)}}main{{max-width:1232px;margin:auto;padding:0 40px}}nav{{display:flex;gap:22px;flex-wrap:wrap;padding:22px 0;border-bottom:1px solid #ccd5d4;font:12px ui-monospace,monospace}}nav a{{text-decoration:none}}section{{padding:44px 0 48px;border-bottom:1px solid #bfcacb;scroll-margin-top:15px}}.section-head{{display:grid;grid-template-columns:84px 1fr;align-items:baseline;margin-bottom:24px}}.index{{font:13px ui-monospace,monospace;color:var(--red)}}h1{{font-weight:500;font-size:clamp(36px,5vw,66px);line-height:1.06;letter-spacing:-2.4px;max-width:900px;margin:32px 0 20px}}h2{{font-weight:500;font-size:29px;line-height:1.2;margin:0;letter-spacing:-.5px}}h3{{font-size:17px;font-weight:600;margin:0 0 10px}}p{{max-width:860px;margin:12px 0 18px}}.lead{{font-size:18px;max-width:850px}}.meta{{font:12px ui-monospace,monospace;text-transform:uppercase;letter-spacing:1px;color:var(--muted)}}.facts{{display:flex;gap:38px;flex-wrap:wrap;margin-top:24px;padding-top:20px;border-top:1px solid #d3dad7}}.facts strong{{display:block;font-size:25px;font-weight:500}}.facts span{{font:12px ui-monospace,monospace;color:var(--muted)}}figure{{margin:20px 0 4px}}figure img{{display:block;width:100%;height:auto}}figcaption{{font-size:13px;color:var(--muted);margin-top:4px}}.two{{display:grid;grid-template-columns:minmax(0,1.1fr) minmax(0,1fr);gap:52px}}.table-scroll{{overflow-x:auto;max-width:100%}}table{{border-collapse:collapse;width:100%;font-size:14px}}th,td{{padding:12px 13px;border-bottom:1px solid #d4dcd9;text-align:left;vertical-align:top}}th{{font-weight:500}}thead th{{font:11px ui-monospace,monospace;text-transform:uppercase;color:var(--muted)}}td strong{{font-size:25px;font-weight:500}}td small{{display:block;color:var(--muted)}}.selected{{background:#e5eef0;color:var(--blue)}}.formula{{font:18px ui-monospace,monospace;padding:22px 0;color:var(--blue);overflow-wrap:anywhere}}pre{{font:13px/1.8 ui-monospace,monospace;padding:20px;background:#e9edeb;white-space:pre-wrap;overflow-wrap:anywhere;margin:14px 0}}.note{{border-left:2px solid var(--red);padding-left:18px;font-size:14px}}.small{{font-size:13px;color:var(--muted)}}.links{{display:flex;gap:20px;flex-wrap:wrap;font-size:13px;margin-top:22px}}footer{{padding:24px 0 45px;font-size:12px;color:var(--muted)}}code{{overflow-wrap:anywhere}}@media(max-width:700px){{main{{padding:0 18px}}nav{{gap:15px}}section{{padding:32px 0}}.section-head{{grid-template-columns:40px 1fr}}h1{{letter-spacing:-1.3px}}h2{{font-size:24px}}.two{{grid-template-columns:1fr;gap:24px}}.facts{{gap:23px}}th,td{{padding:10px 8px}}.table-scroll table{{min-width:440px}}}}
</style></head><body><main>
<section id="overview"><nav><a href="#overview">01 Network</a><a href="#rerouting">02 Rerouting</a><a href="#allocation">03 Allocation</a><a href="#certificates">04 Certificates</a><a href="#feasibility">05 Limits</a><a href="#validation">06 Validation</a></nav>
<div class="meta" style="margin-top:30px">Operations research / exact integer optimization</div><h1>Capacitated<br>minimum-cost flow</h1><p class="lead">A feasible flow is improved by cancelling negative-cost residual cycles. Every terminal claim is checked from the original network and a separate certificate.</p>
<figure><img src="figures/transportation.svg" alt="Optimal transportation network with three warehouses, three demand nodes and ten units of flow"><figcaption>Transportation fixture: actual final flow. Zero-flow allocation arcs are omitted here and retained in the full cost table below.</figcaption></figure>
<div class="facts"><div><strong>20</strong><span>TRANSPORT COST</span></div><div><strong>10 / 10</strong><span>UNITS DELIVERED</span></div><div><strong>8</strong><span>FIXED SCENARIOS</span></div><div><strong>Exact integers</strong><span>CAPACITY / COST / FLOW</span></div></div></section>
<section id="rerouting"><div class="section-head"><span class="index">02</span><h2>Rerouting through reverse edges</h2></div><p>Breadth-first search first selects <code>s → a → t</code>, with cost 10. The residual cycle uses two reverse arcs to remove that choice and two forward arcs to send the same unit along the cost-1 route.</p><figure><img src="figures/rerouting.svg" alt="Three panels show the initial flow, negative-cost residual cycle and final optimal flow"><figcaption>Actual trace: one augmentation followed by one cancellation. A reverse residual edge subtracts original flow; it is distinct from an original antiparallel edge.</figcaption></figure><div class="two"><pre>delivered: 1 → 1\ncycle amount: 1\ncycle unit cost: -9\nobjective: 10 → 1</pre><p class="note">The cancellation changes the allocation while preserving conservation at every node. Final residual reduced costs are all nonnegative, so no further negative cycle exists.</p></div></section>
<section id="allocation"><div class="section-head"><span class="index">03</span><h2>Transportation allocation</h2></div><div class="two"><div><div class="table-scroll"><table><thead><tr><th>Warehouse</th><th>D1 · 3 units</th><th>D2 · 4 units</th><th>D3 · 3 units</th></tr></thead><tbody>{allocation}</tbody></table></div><p class="small">Cell: allocated units, then unit cost. Each allocation arc has capacity 10; source and sink arcs impose warehouse supply and destination demand.</p><div class="formula">4 × 2 + 3 × 3 + 3 × 1 = 20</div></div><div><h3>Observed optimization steps</h3><p>The deterministic initial allocation costs {next(event["objective"] for event in reversed(transport["trace"]) if event["kind"] == "AUGMENT")}. The solver then performs {transport["counts"]["cancellations"]} cycle cancellations to reach cost 20.</p><p>The optimum is independently supported by the residual-potential certificate, rather than by the apparent quality of the allocation.</p><pre>minimize  Σ cost[e] × flow[e]\nsubject to  0 ≤ flow[e] ≤ capacity[e]\noutflow − inflow = 10 at s\noutflow − inflow = -10 at t\noutflow − inflow = 0 elsewhere</pre></div></div></section>
<section id="certificates"><div class="section-head"><span class="index">04</span><h2>Primal and residual certificates</h2></div><p>The verifier reads only the original network and result. It checks every capacity, every node balance, the exact objective, and every positive-capacity residual edge. It does not call the solver's BFS or Bellman–Ford routines.</p><div class="formula">reduced_cost(u,v) = cost(u,v) + p[u] − p[v] ≥ 0</div><div class="two"><div><h3>Transportation node checks</h3><div class="table-scroll"><table><thead><tr><th>Node</th><th>Potential</th><th>Net outflow</th></tr></thead><tbody>{potential_rows}</tbody></table></div></div><div><h3>Rerouting residual-edge checks</h3><div class="table-scroll"><table><thead><tr><th>Residual arc</th><th>Cost</th><th>p[u]</th><th>p[v]</th><th>Reduced</th></tr></thead><tbody>{residual_rows}</tbody></table></div><p class="note">Potential differences telescope around any cycle. Nonnegative reduced residual costs therefore exclude a negative-cost cycle. Together with feasibility, this certifies a minimum-cost flow of the required value.</p><p class="small">The transportation certificate checks {transport["verification"]["residual_edges_checked"]} residual arcs. These are mathematical certificates for this bounded model.</p></div></div></section>
<section id="feasibility"><div class="section-head"><span class="index">05</span><h2>Infeasibility and budget limits</h2></div><figure><img src="figures/cut.svg" alt="Source-side cut of capacity four prevents a request of five units"><figcaption>Infeasible fixture: the two red cut-crossing arcs have capacities 1 and 3. A feasible four-unit flow and this capacity-four cut certify that five units cannot be delivered.</figcaption></figure><div class="two"><div><h3>INFEASIBLE</h3><pre>required: 5\ndelivered: 4\ncut source side: {esc(failed["certificate"]["source_side"])}\ncut capacity: 4</pre></div><div><h3>UNKNOWN</h3><p>A zero cancellation budget leaves the rerouting case at cost 10. The flow meets the required amount, but a negative cycle remains. The result certifies a feasible incumbent only.</p><p class="note">Negative-cost cycles are supported, including disconnected bounded circulations. Zero required transfer can therefore have negative optimal cost. Self-loops, lower bounds and unbounded capacities are outside this model.</p></div></div></section>
<section id="validation"><div class="section-head"><span class="index">06</span><h2>Validation and local measurements</h2></div><div class="table-scroll"><table><thead><tr><th>Scenario</th><th>Status</th><th>Flow / request</th><th>Objective</th><th>Cancellations</th></tr></thead><tbody>{result_rows}</tbody></table></div><figure><img src="figures/timings.svg" alt="Measured local solve duration distributions for eight scenarios"><figcaption>{env["timing"]["samples_per_case"]} calls per case after three untimed warmups, in a seeded interleaved order. Timings include trace construction and exclude parsing, serialization and verification.</figcaption></figure><p><strong>650 randomized unit-test networks</strong> are compared with exhaustive assignment enumeration. A separate preserved corpus contains <strong>{env["oracle"]["cases"]} networks / {env["oracle"]["assignments"]:,} assignments</strong>, including negative costs, zero capacities, parallel arcs and disconnected components.</p><p class="small">These tiny local synthetic measurements are not production benchmarks. Cycle cancellation is pseudopolynomial without the explicit budget; tie-breaking and input order influence work. Source hashes, every input, exact traces, certificates and raw timing rows are retained.</p><div class="links"><a href="../results/summary.json">Results JSON</a><a href="../results/timings.csv">Timing samples</a><a href="../results/oracle-corpus.json">Oracle corpus</a><a href="../results/provenance.json">Provenance</a><a href="methodology.md">Methodology</a></div></section>
<footer>Synthetic operations-research exercise · AI-assisted implementation and documentation · Python standard library · No external optimizer.</footer>
</main></body></html>"""
    html_report = html_report.replace(
        '<div class="table-scroll">',
        '<div class="table-scroll" tabindex="0" role="region" aria-label="Scrollable result table">',
    )
    html_report = html_report.replace(
        "</style>",
        ".two>*{min-width:0}.table-scroll:focus-visible{outline:2px solid var(--blue);outline-offset:3px}</style>",
    )
    write(out / "docs/report.html", html_report)

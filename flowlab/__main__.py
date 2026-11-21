"""JSON CLI with concise diagnostics and explicit terminal-status exit codes."""

import argparse
import json
from pathlib import Path
import sys

from .model import from_dict
from .solver import solve
from .verify import verify


def unique_object(pairs: list) -> dict:
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON member: {key}")
        value[key] = item
    return value


def load(path: Path) -> dict:
    if path.stat().st_size > 256_000:
        raise ValueError("input exceeds 256 KB")

    def reject_constant(value: str) -> None:
        raise ValueError(f"invalid JSON number: {value}")

    return json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=unique_object,
        parse_constant=reject_constant,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Exact integer min-cost flow and certificate verification"
    )
    parser.add_argument("input", type=Path)
    parser.add_argument("--cycle-budget", type=int, default=10_000)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--verify", type=Path, help="verify an existing result instead of solving"
    )
    args = parser.parse_args()
    try:
        network = from_dict(load(args.input))
        if args.verify:
            result = verify(network, load(args.verify))
            code = 0
        else:
            result = solve(network, args.cycle_budget)
            result["verification"] = verify(network, result)
            code = {"OPTIMAL": 0, "INFEASIBLE": 3, "UNKNOWN": 4}[result["status"]]
        text = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(text, encoding="utf-8", newline="\n")
        else:
            sys.stdout.write(text)
        return code
    except (OSError, ValueError, TypeError) as error:
        print(f"flowlab: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

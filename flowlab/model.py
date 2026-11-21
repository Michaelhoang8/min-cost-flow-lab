"""Validated immutable inputs. Capacities and costs use exact Python integers."""

from dataclasses import dataclass
import re


def integer(value: object, name: str, low: int, high: int) -> int:
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{name} must be an integer in [{low}, {high}]")
    return value


def name(value: object) -> str:
    if not isinstance(value, str) or not re.fullmatch(
        r"[A-Za-z][A-Za-z0-9_-]{0,31}", value
    ):
        raise ValueError(
            "identifiers must be 1..32 ASCII letters, digits, '_' or '-'; start with a letter"
        )
    return value


@dataclass(frozen=True)
class Arc:
    id: str
    tail: str
    head: str
    capacity: int
    cost: int


@dataclass(frozen=True)
class Network:
    nodes: tuple[str, ...]
    arcs: tuple[Arc, ...]
    source: str
    sink: str
    required: int

    def __post_init__(self) -> None:
        if type(self.nodes) is not tuple or not 2 <= len(self.nodes) <= 32:
            raise ValueError("nodes must be a tuple of 2..32 identifiers")
        for node in self.nodes:
            name(node)
        if len(set(self.nodes)) != len(self.nodes):
            raise ValueError("duplicate node")
        if (
            self.source not in self.nodes
            or self.sink not in self.nodes
            or self.source == self.sink
        ):
            raise ValueError("source and sink must be distinct listed nodes")
        integer(self.required, "required", 0, 10_000)
        if type(self.arcs) is not tuple or len(self.arcs) > 128:
            raise ValueError("arcs must be a tuple of at most 128 Arc objects")
        seen = set()
        for arc in self.arcs:
            if type(arc) is not Arc:
                raise ValueError("arcs must contain Arc objects")
            name(arc.id)
            if arc.id in seen:
                raise ValueError("duplicate arc id")
            seen.add(arc.id)
            if (
                arc.tail not in self.nodes
                or arc.head not in self.nodes
                or arc.tail == arc.head
            ):
                raise ValueError(
                    "arcs need distinct listed endpoints; self loops are unsupported"
                )
            integer(arc.capacity, "capacity", 0, 10_000)
            integer(arc.cost, "cost", -10_000, 10_000)

    def to_dict(self) -> dict:
        return {
            "format": 1,
            "nodes": list(self.nodes),
            "source": self.source,
            "sink": self.sink,
            "required": self.required,
            "arcs": [dict(vars(arc)) for arc in self.arcs],
        }


def from_dict(value: object) -> Network:
    expected = {"format", "nodes", "arcs", "source", "sink", "required"}
    if (
        not isinstance(value, dict)
        or set(value) != expected
        or type(value["format"]) is not int
        or value["format"] != 1
    ):
        raise ValueError(
            "expected format 1 and exactly nodes/arcs/source/sink/required"
        )
    if not isinstance(value["nodes"], list) or not isinstance(value["arcs"], list):
        raise ValueError("nodes and arcs must be arrays")
    arcs = []
    for item in value["arcs"]:
        if not isinstance(item, dict) or set(item) != {
            "id",
            "tail",
            "head",
            "capacity",
            "cost",
        }:
            raise ValueError("arc fields must be id/tail/head/capacity/cost")
        arcs.append(Arc(**item))
    return Network(
        tuple(value["nodes"]),
        tuple(arcs),
        value["source"],
        value["sink"],
        value["required"],
    )

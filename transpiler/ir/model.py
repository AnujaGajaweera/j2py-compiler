from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass(slots=True)
class IRInstruction:
    op: str
    args: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class IRBlock:
    name: str
    instructions: list[IRInstruction] = field(default_factory=list)


@dataclass(slots=True)
class IRFunction:
    name: str
    params: list[str]
    return_type: str
    blocks: list[IRBlock]
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class IRClass:
    name: str
    kind: str
    bases: list[str]
    fields: list[dict[str, object]]
    methods: list[IRFunction]
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class IRModule:
    name: str
    package: str | None
    classes: list[IRClass]
    metadata: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


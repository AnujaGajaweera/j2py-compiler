from __future__ import annotations

from dataclasses import dataclass, field

from transpiler.ast_nodes import CompilationUnit
from transpiler.diagnostics import Diagnostic


@dataclass(slots=True)
class TypeInfo:
    name: str
    python_type: str
    generic_args: list[str] = field(default_factory=list)


@dataclass(slots=True)
class Symbol:
    name: str
    kind: str
    type_info: TypeInfo
    owner: str | None = None
    is_static: bool = False


@dataclass(slots=True)
class SemanticModel:
    compilation_unit: CompilationUnit
    symbols: dict[str, Symbol]
    type_graph: dict[str, list[str]]
    call_graph: dict[str, list[str]]
    dependency_graph: dict[str, list[str]]
    diagnostics: list[Diagnostic] = field(default_factory=list)
    facts: dict[str, object] = field(default_factory=dict)


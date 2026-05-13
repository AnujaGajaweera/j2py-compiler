from __future__ import annotations

from dataclasses import dataclass, field

from transpiler.ast_nodes import CompilationUnit
from transpiler.diagnostics import Diagnostic


@dataclass(slots=True)
class FrontendArtifact:
    unit_path: str
    ast: CompilationUnit | None = None
    diagnostics: list[Diagnostic] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)
    frontend_name: str = "unknown"


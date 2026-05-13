from __future__ import annotations

from transpiler.diagnostics import DiagnosticBag
from .jdt_bridge import JdtBridge
from .java_subset import parse_subset
from .model import FrontendArtifact


class SourceFrontend:
    def __init__(self, jdt_bridge: JdtBridge | None = None) -> None:
        self.jdt_bridge = jdt_bridge or JdtBridge()

    def parse(self, source_path: str) -> FrontendArtifact:
        diagnostics = DiagnosticBag()
        ast, bridge_diagnostics = self.jdt_bridge.parse(source_path)
        diagnostics.extend(bridge_diagnostics)
        if ast is None:
            ast = parse_subset(source_path)
            frontend_name = "python-subset"
        else:
            frontend_name = "eclipse-jdt"
        return FrontendArtifact(
            unit_path=source_path,
            ast=ast,
            diagnostics=diagnostics.items,
            frontend_name=frontend_name,
        )


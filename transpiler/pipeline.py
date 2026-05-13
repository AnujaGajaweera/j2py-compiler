from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from transpiler.backend.python.emitter import PythonEmitter
from transpiler.build.discovery import discover_project
from transpiler.build.model import ProjectUnit, SourceUnit
from transpiler.diagnostics import Diagnostic, Severity
from transpiler.frontend import BytecodeFrontend, SourceFrontend
from transpiler.ir import IRLowerer
from transpiler.optimizer import PassManager
from transpiler.plugins import BuiltinFrameworkDetector
from transpiler.semantic import SemanticAnalyzer


@dataclass(slots=True)
class CompilerSettings:
    output_dir: Path = Path("out")
    emit_ir: bool = True
    optimize: bool = True


@dataclass(slots=True)
class CompilationResult:
    project: ProjectUnit
    emitted_files: list[Path] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)
    reports: dict[str, object] = field(default_factory=dict)


class CompilerPipeline:
    def __init__(self, settings: CompilerSettings | None = None) -> None:
        self.settings = settings or CompilerSettings()
        self.source_frontend = SourceFrontend()
        self.bytecode_frontend = BytecodeFrontend()
        self.semantic = SemanticAnalyzer()
        self.lowerer = IRLowerer()
        self.optimizer = PassManager()
        self.emitter = PythonEmitter()
        self.detector = BuiltinFrameworkDetector()

    def compile(self, target: str | Path) -> CompilationResult:
        project = discover_project(target)
        result = CompilationResult(project=project)
        for unit in project.sources:
            self._compile_unit(unit, result)
        if result.reports:
            reports_path = self.settings.output_dir / "report.json"
            reports_path.parent.mkdir(parents=True, exist_ok=True)
            reports_path.write_text(json.dumps(result.reports, indent=2), encoding="utf-8")
            result.emitted_files.append(reports_path)
        return result

    def analyze(self, target: str | Path) -> CompilationResult:
        project = discover_project(target)
        result = CompilationResult(project=project)
        for unit in project.sources:
            artifact = self._load_frontend_artifact(unit)
            result.diagnostics.extend(artifact.diagnostics)
            if artifact.ast is None:
                continue
            semantic_model = self.semantic.analyze(artifact.ast)
            result.diagnostics.extend(semantic_model.diagnostics)
            result.reports[str(unit.path)] = {
                "frontend": artifact.frontend_name,
                "frameworks": self.detector.detect(semantic_model),
                "facts": semantic_model.facts,
                "symbols": sorted(semantic_model.symbols),
            }
        return result

    def inspect_ir(self, target: str | Path) -> dict[str, object]:
        project = discover_project(target)
        ir_dump: dict[str, object] = {}
        for unit in project.sources:
            artifact = self._load_frontend_artifact(unit)
            if artifact.ast is None:
                continue
            semantic_model = self.semantic.analyze(artifact.ast)
            module = self.lowerer.lower(semantic_model)
            if self.settings.optimize:
                module = self.optimizer.run(module)
            ir_dump[str(unit.path)] = module.to_dict()
        return ir_dump

    def _compile_unit(self, unit: SourceUnit, result: CompilationResult) -> None:
        artifact = self._load_frontend_artifact(unit)
        result.diagnostics.extend(artifact.diagnostics)
        if artifact.ast is None:
            return
        semantic_model = self.semantic.analyze(artifact.ast)
        result.diagnostics.extend(semantic_model.diagnostics)
        module = self.lowerer.lower(semantic_model)
        if self.settings.optimize:
            module = self.optimizer.run(module)
        emitted = self.emitter.emit(module, self.settings.output_dir)
        result.emitted_files.extend(item.path for item in emitted)
        result.reports[str(unit.path)] = {
            "frontend": artifact.frontend_name,
            "frameworks": self.detector.detect(semantic_model),
            "facts": semantic_model.facts,
            "dependency_graph": semantic_model.dependency_graph,
        }
        if semantic_model.facts.get("uses_reflection"):
            result.diagnostics.append(
                Diagnostic(
                    code="PIPE001",
                    message="Reflection usage detected; generated Python may require manual review.",
                    severity=Severity.WARNING,
                    category="native-translation-gap",
                    fallback="Emit TODO markers and inspect report.json.",
                )
            )

    def _load_frontend_artifact(self, unit: SourceUnit):
        if unit.kind == "java":
            return self.source_frontend.parse(str(unit.path))
        if unit.kind in {"class", "jar"}:
            return self.bytecode_frontend.analyze(str(unit.path))
        raise ValueError(f"Unsupported input kind: {unit.kind}")


from __future__ import annotations

from transpiler.semantic.model import SemanticModel


class BuiltinFrameworkDetector:
    def detect(self, semantic_model: SemanticModel) -> list[str]:
        findings: list[str] = []
        imports = semantic_model.compilation_unit.imports
        decl_names = [decl.name for decl in semantic_model.compilation_unit.declarations]
        if any("springframework" in item for item in imports):
            findings.append("spring")
        if any(name.endswith("Controller") for name in decl_names):
            findings.append("controller")
        if any(name.endswith("Service") for name in decl_names):
            findings.append("service")
        if any("lwjgl" in item.lower() for item in imports):
            findings.append("lwjgl")
        if semantic_model.facts.get("uses_concurrency"):
            findings.append("concurrency")
        if semantic_model.facts.get("uses_reflection"):
            findings.append("reflection")
        return findings

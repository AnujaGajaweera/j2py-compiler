from __future__ import annotations

import re

from transpiler.ast_nodes import CompilationUnit, MethodDecl, TypeDecl
from transpiler.diagnostics import DiagnosticBag, Severity

from .model import SemanticModel, Symbol, TypeInfo


JAVA_TO_PYTHON_TYPES = {
    "int": "int",
    "long": "int",
    "double": "float",
    "float": "float",
    "boolean": "bool",
    "String": "str",
    "void": "None",
    "ArrayList": "list",
    "List": "list",
    "HashMap": "dict",
    "Map": "dict",
    "HashSet": "set",
    "Set": "set",
}


class SemanticAnalyzer:
    def analyze(self, unit: CompilationUnit) -> SemanticModel:
        diagnostics = DiagnosticBag()
        symbols: dict[str, Symbol] = {}
        type_graph: dict[str, list[str]] = {}
        call_graph: dict[str, list[str]] = {}
        dependency_graph: dict[str, list[str]] = {}
        facts = {"uses_reflection": False, "uses_concurrency": False, "uses_streams": False}

        for decl in unit.declarations:
            type_graph[decl.name] = list(decl.bases)
            symbols[decl.name] = Symbol(decl.name, decl.kind, TypeInfo(decl.name, decl.name))
            dependency_graph[decl.name] = []
            for field in decl.fields:
                symbols[f"{decl.name}.{field.name}"] = Symbol(
                    name=field.name,
                    kind="field",
                    type_info=_map_type(field.type_ref.name, field.type_ref),
                    owner=decl.name,
                    is_static=field.is_static,
                )
            for method in decl.methods:
                full_name = f"{decl.name}.{method.name}"
                symbols[full_name] = Symbol(
                    name=method.name,
                    kind="method",
                    type_info=_map_type(method.return_type.name, method.return_type),
                    owner=decl.name,
                    is_static=method.is_static,
                )
                for param in method.params:
                    symbols[f"{decl.name}.{method.name}.{param.name}"] = Symbol(
                        name=param.name,
                        kind="parameter",
                        type_info=_map_type(param.type_ref.name, param.type_ref),
                        owner=full_name,
                        is_static=False,
                    )
                call_graph[full_name] = _extract_calls(method)
                dependency_graph[decl.name].extend(_extract_dependencies(method))
                facts["uses_reflection"] = facts["uses_reflection"] or _mentions(method, ["Class.forName", ".invoke(", ".getField("])
                facts["uses_concurrency"] = facts["uses_concurrency"] or _mentions(
                    method,
                    ["Thread", "ExecutorService", "CompletableFuture", "synchronized", "volatile"],
                )
                facts["uses_streams"] = facts["uses_streams"] or _mentions(method, [".stream()", ".filter(", ".map("])
                if len({param.name for param in method.params}) != len(method.params):
                    diagnostics.add(
                        code="SEM001",
                        message=f"Duplicate parameter name in {full_name}",
                        severity=Severity.ERROR,
                        category="semantic",
                    )
            if decl.kind == "interface":
                diagnostics.add(
                    code="SEM002",
                    message=f"Interface {decl.name} will be lowered to ABC/Protocol based on usage.",
                    severity=Severity.INFO,
                    category="semantic",
                )

        for decl_name, deps in dependency_graph.items():
            dependency_graph[decl_name] = sorted(set(dep for dep in deps if dep != decl_name))
        source_text = unit.raw_source
        facts["uses_reflection"] = facts["uses_reflection"] or any(
            needle in source_text for needle in ["java.lang.reflect", "Class.forName", "getDeclaredMethods", ".invoke("]
        )
        facts["uses_concurrency"] = facts["uses_concurrency"] or any(
            needle in source_text for needle in ["new Thread(", "CompletableFuture", "synchronized", "ExecutorService", "volatile"]
        )
        facts["uses_streams"] = facts["uses_streams"] or ".stream()" in source_text

        return SemanticModel(
            compilation_unit=unit,
            symbols=symbols,
            type_graph=type_graph,
            call_graph=call_graph,
            dependency_graph=dependency_graph,
            diagnostics=diagnostics.items,
            facts=facts,
        )


def _map_type(name: str, type_ref) -> TypeInfo:
    python_type = JAVA_TO_PYTHON_TYPES.get(name, name)
    generic_args = [JAVA_TO_PYTHON_TYPES.get(arg.name, arg.name) for arg in type_ref.type_args]
    return TypeInfo(name=name, python_type=python_type, generic_args=generic_args)


def _extract_calls(method: MethodDecl) -> list[str]:
    calls: list[str] = []
    for stmt in method.body:
        calls.extend(match.group(1) for match in re.finditer(r"(\w+)\s*\(", stmt.text))
    return calls


def _extract_dependencies(method: MethodDecl) -> list[str]:
    deps: list[str] = []
    for stmt in method.body:
        deps.extend(match.group(1) for match in re.finditer(r"\b([A-Z]\w+)\b", stmt.text))
    return deps


def _mentions(method: MethodDecl, needles: list[str]) -> bool:
    joined = "\n".join(stmt.text for stmt in method.body)
    return any(needle in joined for needle in needles)

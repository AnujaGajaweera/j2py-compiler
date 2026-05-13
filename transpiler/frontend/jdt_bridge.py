from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from transpiler.ast_nodes import CompilationUnit
from transpiler.diagnostics import Diagnostic, Severity


class JdtBridge:
    def __init__(self, jar_path: str | None = None) -> None:
        self.jar_path = jar_path or os.getenv("J2PY_JDT_JAR")

    @property
    def available(self) -> bool:
        return bool(self.jar_path and Path(self.jar_path).exists())

    def parse(self, source_path: str) -> tuple[CompilationUnit | None, list[Diagnostic]]:
        if not self.available:
            return None, [
                Diagnostic(
                    code="JDT001",
                    message="Eclipse JDT jar not configured; using subset frontend fallback.",
                    severity=Severity.INFO,
                    fallback="Set J2PY_JDT_JAR to enable the primary source frontend.",
                    category="frontend",
                )
            ]

        command = ["java", "-cp", self.jar_path, "transpiler.jdt.BridgeMain", source_path]
        try:
            completed = subprocess.run(command, check=True, capture_output=True, text=True, timeout=30)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as exc:
            return None, [
                Diagnostic(
                    code="JDT002",
                    message=f"JDT bridge failed: {exc}",
                    severity=Severity.WARNING,
                    fallback="Falling back to the built-in subset frontend.",
                    category="frontend",
                )
            ]

        payload = json.loads(completed.stdout)
        return _compilation_unit_from_json(payload), []


def _compilation_unit_from_json(payload: dict[str, object]) -> CompilationUnit:
    from transpiler.ast_nodes import CompilationUnit, FieldDecl, JavaTypeRef, MethodDecl, Parameter, Statement, TypeDecl

    declarations: list[TypeDecl] = []
    for decl in payload.get("declarations", []):
        methods = [
            MethodDecl(
                name=method["name"],
                return_type=JavaTypeRef(method["return_type"]),
                params=[Parameter(p["name"], JavaTypeRef(p["type"])) for p in method.get("params", [])],
                body=[Statement(stmt["kind"], stmt["text"]) for stmt in method.get("body", [])],
                is_static=method.get("is_static", False),
                is_abstract=method.get("is_abstract", False),
            )
            for method in decl.get("methods", [])
        ]
        fields = [
            FieldDecl(
                name=field["name"],
                type_ref=JavaTypeRef(field["type"]),
                initializer=field.get("initializer"),
                is_static=field.get("is_static", False),
            )
            for field in decl.get("fields", [])
        ]
        declarations.append(
            TypeDecl(
                name=decl["name"],
                kind=decl["kind"],
                fields=fields,
                methods=methods,
                bases=decl.get("bases", []),
                modifiers=decl.get("modifiers", []),
            )
        )
    return CompilationUnit(
        path=str(payload["path"]),
        package=payload.get("package"),
        imports=list(payload.get("imports", [])),
        declarations=declarations,
    )


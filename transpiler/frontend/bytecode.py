from __future__ import annotations

import re
import subprocess
from pathlib import Path

from transpiler.ast_nodes import CompilationUnit, MethodDecl, TypeDecl, JavaTypeRef
from transpiler.diagnostics import Diagnostic, Severity

from .model import FrontendArtifact


class BytecodeFrontend:
    def analyze(self, path: str) -> FrontendArtifact:
        target = Path(path)
        command = ["javap", "-classpath", str(target.parent), "-c", "-p", target.stem]
        try:
            completed = subprocess.run(command, check=True, capture_output=True, text=True, timeout=30)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as exc:
            return FrontendArtifact(
                unit_path=path,
                diagnostics=[
                    Diagnostic(
                        code="BYTE001",
                        message=f"Bytecode analysis failed: {exc}",
                        severity=Severity.ERROR,
                        category="bytecode",
                    )
                ],
                frontend_name="javap",
            )

        ast = _parse_javap_output(target, completed.stdout)
        return FrontendArtifact(unit_path=path, ast=ast, frontend_name="javap", metadata={"disassembly": completed.stdout})


def _parse_javap_output(path: Path, output: str) -> CompilationUnit:
    class_name = path.stem
    method_names = re.findall(r"\n\s+(?:public|private|protected).*?(\w+)\([^)]*\);", output)
    methods = [
        MethodDecl(name=name, return_type=JavaTypeRef("Object"), params=[], body=[], is_static=False, is_abstract=False)
        for name in method_names
        if name != class_name
    ]
    return CompilationUnit(
        path=str(path.resolve()),
        package=None,
        imports=[],
        declarations=[TypeDecl(name=class_name, kind="class", methods=methods)],
    )


from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class JavaTypeRef:
    name: str
    type_args: list["JavaTypeRef"] = field(default_factory=list)
    array_dims: int = 0


@dataclass(slots=True)
class CompilationUnit:
    path: str
    package: str | None
    imports: list[str]
    declarations: list["TypeDecl"]
    raw_source: str = ""


@dataclass(slots=True)
class Parameter:
    name: str
    type_ref: JavaTypeRef


@dataclass(slots=True)
class FieldDecl:
    name: str
    type_ref: JavaTypeRef
    initializer: str | None = None
    is_static: bool = False


@dataclass(slots=True)
class MethodDecl:
    name: str
    return_type: JavaTypeRef
    params: list[Parameter]
    body: list["Statement"]
    is_static: bool = False
    is_abstract: bool = False
    raw_body: str = ""


@dataclass(slots=True)
class TypeDecl:
    name: str
    kind: str
    fields: list[FieldDecl] = field(default_factory=list)
    methods: list[MethodDecl] = field(default_factory=list)
    bases: list[str] = field(default_factory=list)
    modifiers: list[str] = field(default_factory=list)


@dataclass(slots=True)
class Statement:
    kind: str
    text: str
    children: list["Statement"] = field(default_factory=list)
    else_children: list["Statement"] = field(default_factory=list)
    metadata: dict[str, object] = field(default_factory=dict)

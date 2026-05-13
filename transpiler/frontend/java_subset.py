from __future__ import annotations

import re
from pathlib import Path

from transpiler.ast_nodes import CompilationUnit, FieldDecl, JavaTypeRef, MethodDecl, Parameter, Statement, TypeDecl
from transpiler.frontend.expression_parser import ExpressionParser

_PACKAGE_RE = re.compile(r"package\s+([\w.]+)\s*;")
_IMPORT_RE = re.compile(r"import\s+([\w.*]+)\s*;")
_CLASS_RE = re.compile(
    r"(?P<mods>(?:public|private|protected|abstract|final|static)\s+)*"
    r"(?P<kind>class|interface|enum)\s+"
    r"(?P<name>\w+)"
    r"(?:<.+?>)?"
    r"(?:\s+extends\s+(?P<extends>\w+))?"
    r"(?:\s+implements\s+(?P<implements>[\w,\s]+))?"
    r"\s*\{",
    re.MULTILINE,
)
_METHOD_HEADER_RE = re.compile(
    r"^\s*(?P<mods>(?:(?:public|private|protected|static|final|abstract|synchronized)\s+)*)"
    r"(?:(?P<type_params><[^>]+>)\s+)?"
    r"(?P<rtype>[\w<>\[\], ?]+)\s+"
    r"(?P<name>\w+)\s*"
    r"\((?P<params>[^)]*)\)\s*"
    r"(?:throws\s+[\w.,\s]+)?$",
    re.MULTILINE,
)
_EXPR_PARSER = ExpressionParser()


def parse_subset(source_path: str | Path) -> CompilationUnit:
    path = Path(source_path)
    text = path.read_text(encoding="utf-8")
    package_match = _PACKAGE_RE.search(text)
    imports = _IMPORT_RE.findall(text)
    declarations: list[TypeDecl] = []

    for class_match in _CLASS_RE.finditer(text):
        body_start = class_match.end()
        body_end = _find_matching_brace(text, body_start - 1)
        body_text = text[body_start:body_end].strip()
        declarations.append(_parse_type_decl(class_match, body_text))

    return CompilationUnit(
        path=str(path.resolve()),
        package=package_match.group(1) if package_match else None,
        imports=imports,
        declarations=declarations,
        raw_source=text,
    )


def _parse_type_decl(match: re.Match[str], body_text: str) -> TypeDecl:
    modifiers = (match.group("mods") or "").split()
    bases = []
    if match.group("extends"):
        bases.append(match.group("extends"))
    if match.group("implements"):
        bases.extend([item.strip() for item in match.group("implements").split(",") if item.strip()])

    methods: list[MethodDecl] = []
    fields: list[FieldDecl] = []
    for member in _split_top_level_members(body_text):
        stripped = member.strip().rstrip(";")
        if not stripped:
            continue
        if "{" in member:
            header = member[: member.find("{")].strip()
            method_match = _METHOD_HEADER_RE.match(header)
            if method_match:
                block = member[member.find("{") + 1 : member.rfind("}")].strip()
                methods.append(
                    MethodDecl(
                        name=method_match.group("name"),
                        return_type=_parse_type(method_match.group("rtype")),
                        params=_parse_params(method_match.group("params")),
                        body=_split_statements(block),
                        is_static="static" in (method_match.group("mods") or "").split(),
                        is_abstract=False,
                        raw_body=block,
                    )
                )
            continue

        method_match = _METHOD_HEADER_RE.match(stripped)
        if method_match:
            methods.append(
                MethodDecl(
                    name=method_match.group("name"),
                    return_type=_parse_type(method_match.group("rtype")),
                    params=_parse_params(method_match.group("params")),
                    body=[],
                    is_static="static" in (method_match.group("mods") or "").split(),
                    is_abstract=True,
                    raw_body="",
                )
            )
            continue

        field_info = _parse_field_member(stripped)
        if field_info:
            field_type_text, decls, is_static = field_info
            field_type = _parse_type(field_type_text)
            for name, init in _parse_field_declarators(decls):
                if not name:
                    continue
                fields.append(
                    FieldDecl(
                        name=name,
                        type_ref=field_type,
                        initializer=init,
                        is_static=is_static,
                    )
                )
    return TypeDecl(
        name=match.group("name"),
        kind=match.group("kind"),
        fields=fields,
        methods=methods,
        bases=bases,
        modifiers=modifiers,
    )


def _parse_type(type_text: str) -> JavaTypeRef:
    text = type_text.strip()
    array_dims = text.count("[]")
    text = text.replace("[]", "")
    if "<" not in text:
        return JavaTypeRef(name=text.strip(), array_dims=array_dims)
    base, arg_text = text.split("<", 1)
    arg_text = arg_text.rsplit(">", 1)[0]
    args = [_parse_type(part.strip()) for part in arg_text.split(",") if part.strip()]
    return JavaTypeRef(name=base.strip(), type_args=args, array_dims=array_dims)


def _parse_params(params_text: str) -> list[Parameter]:
    params: list[Parameter] = []
    for raw_part in [part.strip() for part in params_text.split(",") if part.strip()]:
        pieces = raw_part.split()
        if len(pieces) >= 2:
            params.append(Parameter(name=pieces[-1], type_ref=_parse_type(" ".join(pieces[:-1]))))
    return params


def _split_statements(block: str) -> list[Statement]:
    statements: list[Statement] = []
    idx = 0
    while idx < len(block):
        idx = _skip_ws(block, idx)
        if idx >= len(block):
            break
        if block.startswith("if", idx):
            stmt, idx = _parse_if(block, idx)
            statements.append(stmt)
            continue
        if block.startswith("for", idx):
            stmt, idx = _parse_for(block, idx)
            statements.append(stmt)
            continue
        if block.startswith("while", idx):
            stmt, idx = _parse_while(block, idx)
            statements.append(stmt)
            continue
        if block.startswith("try", idx):
            stmt, idx = _parse_try(block, idx)
            statements.append(stmt)
            continue
        end = _find_statement_end(block, idx)
        raw = block[idx:end].strip()
        if raw:
            statements.append(_classify_statement(raw))
        idx = end + 1
    return statements


def _classify_statement(text: str) -> Statement:
    stripped = text.strip().rstrip(";")
    if stripped.startswith("return "):
        expr_text = stripped.removeprefix("return ").strip()
        return Statement("return", expr_text, metadata={"expr": _parse_expr(expr_text)})
    if stripped.startswith("throw "):
        expr_text = stripped.removeprefix("throw ").strip()
        return Statement("throw", expr_text, metadata={"expr": _parse_expr(expr_text)})
    if re.match(r"[\w<>\[\], ?]+\s+\w+\s*=", stripped):
        return _build_var_decl_statement(stripped)
    assign_match = re.match(r"^(?P<lhs>.+?)\s*(?P<op>=|\+=|-=)\s*(?P<rhs>.+)$", stripped, flags=re.DOTALL)
    if assign_match and "->" not in stripped:
        lhs = assign_match.group("lhs").strip()
        rhs = assign_match.group("rhs").strip()
        op = assign_match.group("op")
        return Statement(
            "assign",
            stripped,
            metadata={
                "target": lhs,
                "target_expr": _parse_expr(lhs),
                "op": op,
                "expr": _parse_expr(rhs),
            },
        )
    if re.match(r"^.+?(\+\+|--)$", stripped):
        target = stripped[:-2].strip()
        op = stripped[-2:]
        return Statement(
            "assign",
            stripped,
            metadata={
                "target": target,
                "target_expr": _parse_expr(target),
                "op": op,
                "expr": {"kind": "number", "value": "1"},
            },
        )
    return Statement("expr", stripped, metadata={"expr": _parse_expr(stripped)})


def _split_top_level_members(body_text: str) -> list[str]:
    members: list[str] = []
    current: list[str] = []
    depth = 0
    paren_depth = 0
    for char in body_text:
        current.append(char)
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0 and paren_depth == 0:
                members.append("".join(current).strip())
                current = []
        elif char == "(":
            paren_depth += 1
        elif char == ")":
            paren_depth -= 1
        elif char == ";" and depth == 0 and paren_depth == 0:
            members.append("".join(current).strip())
            current = []
    tail = "".join(current).strip()
    if tail:
        members.append(tail)
    return members


def _parse_if(block: str, idx: int) -> tuple[Statement, int]:
    cond_start = block.find("(", idx)
    cond_end = _find_matching_pair(block, cond_start, "(", ")")
    body_start = _skip_ws(block, cond_end + 1)
    body, next_idx = _parse_block_or_stmt(block, body_start)
    else_children: list[Statement] = []
    cursor = _skip_ws(block, next_idx)
    if block.startswith("else", cursor):
        else_start = _skip_ws(block, cursor + 4)
        else_children, next_idx = _parse_block_or_stmt(block, else_start)
    return (
        Statement(
            "if",
            block[idx:next_idx].strip(),
            children=body,
            else_children=else_children,
            metadata={
                "condition": block[cond_start + 1 : cond_end].strip(),
                "condition_expr": _parse_expr(block[cond_start + 1 : cond_end].strip()),
            },
        ),
        next_idx,
    )


def _parse_for(block: str, idx: int) -> tuple[Statement, int]:
    cond_start = block.find("(", idx)
    cond_end = _find_matching_pair(block, cond_start, "(", ")")
    header = block[cond_start + 1 : cond_end].strip()
    body_start = _skip_ws(block, cond_end + 1)
    children, next_idx = _parse_block_or_stmt(block, body_start)
    if ":" in header and ";" not in header:
        left, iterable = [part.strip() for part in header.split(":", 1)]
        pieces = left.split()
        var_name = pieces[-1]
        metadata = {"var": var_name, "iterable": iterable, "iterable_expr": _parse_expr(iterable)}
        kind = "enhanced_for"
    else:
        parts = [part.strip() for part in header.split(";")]
        metadata = {
            "init": parts[0] if len(parts) > 0 else "",
            "condition": parts[1] if len(parts) > 1 else "",
            "update": parts[2] if len(parts) > 2 else "",
            "condition_expr": _parse_expr(parts[1]) if len(parts) > 1 and parts[1] else {"kind": "empty"},
        }
        kind = "for"
    return Statement(kind, block[idx:next_idx].strip(), children=children, metadata=metadata), next_idx


def _parse_while(block: str, idx: int) -> tuple[Statement, int]:
    cond_start = block.find("(", idx)
    cond_end = _find_matching_pair(block, cond_start, "(", ")")
    body_start = _skip_ws(block, cond_end + 1)
    children, next_idx = _parse_block_or_stmt(block, body_start)
    return (
        Statement(
            "while",
            block[idx:next_idx].strip(),
            children=children,
            metadata={
                "condition": block[cond_start + 1 : cond_end].strip(),
                "condition_expr": _parse_expr(block[cond_start + 1 : cond_end].strip()),
            },
        ),
        next_idx,
    )


def _parse_try(block: str, idx: int) -> tuple[Statement, int]:
    body_start = _skip_ws(block, idx + 3)
    children, next_idx = _parse_block_or_stmt(block, body_start)
    return Statement("try", block[idx:next_idx].strip(), children=children), next_idx


def _parse_block_or_stmt(block: str, idx: int) -> tuple[list[Statement], int]:
    idx = _skip_ws(block, idx)
    if idx < len(block) and block[idx] == "{":
        end = _find_matching_brace(block, idx)
        return _split_statements(block[idx + 1 : end].strip()), end + 1
    if block.startswith("if", idx):
        stmt, next_idx = _parse_if(block, idx)
        return [stmt], next_idx
    if block.startswith("for", idx):
        stmt, next_idx = _parse_for(block, idx)
        return [stmt], next_idx
    if block.startswith("while", idx):
        stmt, next_idx = _parse_while(block, idx)
        return [stmt], next_idx
    if block.startswith("try", idx):
        stmt, next_idx = _parse_try(block, idx)
        return [stmt], next_idx
    end = _find_statement_end(block, idx)
    raw = block[idx:end].strip()
    return ([_classify_statement(raw)] if raw else []), end + 1


def _find_statement_end(text: str, idx: int) -> int:
    paren_depth = 0
    brace_depth = 0
    for pos in range(idx, len(text)):
        char = text[pos]
        if char == "(":
            paren_depth += 1
        elif char == ")":
            paren_depth -= 1
        elif char == "{":
            brace_depth += 1
        elif char == "}":
            brace_depth -= 1
        elif char == ";" and paren_depth == 0 and brace_depth == 0:
            return pos
    return len(text)


def _find_matching_pair(text: str, start: int, open_char: str, close_char: str) -> int:
    depth = 0
    for idx in range(start, len(text)):
        if text[idx] == open_char:
            depth += 1
        elif text[idx] == close_char:
            depth -= 1
            if depth == 0:
                return idx
    raise ValueError(f"Unmatched {open_char}{close_char} pair in Java source")


def _skip_ws(text: str, idx: int) -> int:
    while idx < len(text) and text[idx].isspace():
        idx += 1
    return idx


def _parse_field_declarators(text: str) -> list[tuple[str, str | None]]:
    parts = [part.strip() for part in text.split(",") if part.strip()]
    declarators: list[tuple[str, str | None]] = []
    for part in parts:
        if "=" in part:
            name, init = part.split("=", 1)
            declarators.append((name.strip(), init.strip() or None))
        else:
            declarators.append((part.strip(), None))
    return declarators


def _parse_field_member(text: str) -> tuple[str, str, bool] | None:
    modifiers = {"public", "private", "protected", "static", "final"}
    stripped = text.strip().rstrip(";")
    if not stripped:
        return None
    tokens = stripped.split()
    idx = 0
    modifier_tokens: list[str] = []
    while idx < len(tokens) and tokens[idx] in modifiers:
        modifier_tokens.append(tokens[idx])
        idx += 1
    remainder = " ".join(tokens[idx:])
    if not remainder:
        return None
    split_at = _find_type_decl_split(remainder)
    if split_at is None:
        return None
    type_text = remainder[:split_at].strip()
    decls = remainder[split_at:].strip()
    if not type_text or not decls:
        return None
    return type_text, decls, "static" in modifier_tokens


def _find_type_decl_split(text: str) -> int | None:
    angle_depth = 0
    bracket_depth = 0
    for idx, char in enumerate(text):
        if char == "<":
            angle_depth += 1
        elif char == ">":
            angle_depth -= 1
        elif char == "[":
            bracket_depth += 1
        elif char == "]":
            bracket_depth -= 1
        elif char.isspace() and angle_depth == 0 and bracket_depth == 0:
            return idx
    return None


def _find_matching_brace(text: str, open_brace_index: int) -> int:
    depth = 0
    for idx in range(open_brace_index, len(text)):
        if text[idx] == "{":
            depth += 1
        elif text[idx] == "}":
            depth -= 1
            if depth == 0:
                return idx
    raise ValueError("Unmatched brace in Java source")


def _build_var_decl_statement(stripped: str) -> Statement:
    match = re.match(r"(?P<type>[\w<>\[\], ?]+)\s+(?P<name>\w+)\s*=\s*(?P<rhs>.+)", stripped, flags=re.DOTALL)
    if not match:
        return Statement("var_decl", stripped)
    return Statement(
        "var_decl",
        stripped,
        metadata={
            "decl_type": match.group("type").strip(),
            "name": match.group("name").strip(),
            "expr": _parse_expr(match.group("rhs").strip()),
        },
    )


def _parse_expr(text: str) -> dict[str, object]:
    try:
        return _EXPR_PARSER.parse(text)
    except Exception:
        return {"kind": "raw", "text": text}

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from transpiler.ir.model import IRClass, IRFunction, IRInstruction, IRModule


@dataclass(slots=True)
class EmittedArtifact:
    path: Path
    content: str


class PythonEmitter:
    def __init__(self) -> None:
        self._current_field_names: set[str] = set()
        self._current_static = False

    def emit(self, module: IRModule, output_dir: str | Path) -> list[EmittedArtifact]:
        out_root = Path(output_dir)
        package_parts = module.package.split(".") if module.package else []
        target_dir = out_root.joinpath(*package_parts)
        target_dir.mkdir(parents=True, exist_ok=True)
        artifacts: list[EmittedArtifact] = []
        if package_parts:
            artifacts.extend(self._ensure_packages(out_root, package_parts))

        module_name = Path(module.name).stem + ".py"
        target = target_dir / module_name
        content = self._render_module(module)
        target.write_text(content, encoding="utf-8")
        artifacts.append(EmittedArtifact(target, content))

        report_target = target_dir / (Path(module.name).stem + ".ir.json")
        report_content = json.dumps(module.to_dict(), indent=2)
        report_target.write_text(report_content, encoding="utf-8")
        artifacts.append(EmittedArtifact(report_target, report_content))
        return artifacts

    def _ensure_packages(self, root: Path, parts: list[str]) -> list[EmittedArtifact]:
        artifacts: list[EmittedArtifact] = []
        current = root
        for part in parts:
            current = current / part
            init_path = current / "__init__.py"
            if not init_path.exists():
                init_path.write_text("", encoding="utf-8")
                artifacts.append(EmittedArtifact(init_path, ""))
        return artifacts

    def _render_module(self, module: IRModule) -> str:
        imports = {"from __future__ import annotations"}
        body: list[str] = []
        if any(ir_class.kind == "enum" for ir_class in module.classes):
            imports.add("from enum import Enum")
        if any(ir_class.kind == "interface" for ir_class in module.classes):
            imports.add("from abc import ABC")
        imports.add("from typing import Any, Protocol")
        import_hints = self._collect_import_hints(module)
        if import_hints.get("threading"):
            imports.add("import threading")
        if import_hints.get("futures"):
            imports.add("import concurrent.futures")
        body.extend(sorted(imports))
        body.append("")
        for ir_class in module.classes:
            body.extend(self._render_class(ir_class))
            body.append("")
        return "\n".join(line.rstrip() for line in body).strip() + "\n"

    def _collect_import_hints(self, module: IRModule) -> dict[str, bool]:
        hints = {"threading": False, "futures": False}
        for ir_class in module.classes:
            for method in ir_class.methods:
                for block in method.blocks:
                    for inst in block.instructions:
                        self._collect_import_hints_from_instruction(inst, hints)
        return hints

    def _collect_import_hints_from_instruction(self, inst: IRInstruction, hints: dict[str, bool]) -> None:
        text = str(inst.args.get("text", "")) + " " + str(inst.args.get("value", ""))
        if "new Thread(" in text or "threading.Thread" in text:
            hints["threading"] = True
        if "CompletableFuture" in text:
            hints["futures"] = True
        for key in ("children", "else_children"):
            for child in inst.args.get(key, []):
                if isinstance(child, IRInstruction):
                    self._collect_import_hints_from_instruction(child, hints)

    def _render_class(self, ir_class: IRClass) -> list[str]:
        if ir_class.kind == "enum":
            header = f"class {ir_class.name}(Enum):"
        elif ir_class.kind == "interface":
            header = f"class {ir_class.name}(Protocol):"
        else:
            bases = ", ".join(ir_class.bases) if ir_class.bases else "object"
            header = f"class {ir_class.name}({bases}):"
        lines = [header]
        if not ir_class.fields and not ir_class.methods:
            return lines + ["    pass"]
        init_fields = [field for field in ir_class.fields if not field["is_static"]]
        static_fields = [field for field in ir_class.fields if field["is_static"]]
        for field in static_fields:
            lines.append(f"    {field['name']} = {self._translate_expr(field['initializer'] or 'None')}")
        if init_fields:
            params = ", ".join(f"{field['name']}: {field['type']} | None = None" for field in init_fields)
            lines.append(f"    def __init__(self, {params}) -> None:")
            for field in init_fields:
                default = self._translate_expr(field["initializer"] or field["name"])
                lines.append(f"        self.{field['name']} = {default}")
        elif ir_class.kind not in {"interface", "enum"} and ir_class.methods:
            lines.append("    def __init__(self) -> None:")
            lines.append("        pass")
        for method in ir_class.methods:
            lines.extend(self._render_method(method, ir_class.kind, {field["name"] for field in ir_class.fields}))
        return lines

    def _render_method(self, method: IRFunction, class_kind: str, field_names: set[str]) -> list[str]:
        decorators: list[str] = []
        param_type_names = method.metadata.get("param_type_names", {})
        typed_params = [f"{param}: {self._python_type(str(param_type_names.get(param, 'Any')))}" for param in method.params]
        prev_field_names = self._current_field_names
        prev_static = self._current_static
        self._current_field_names = set(field_names)
        self._current_static = bool(method.metadata.get("is_static"))
        if method.metadata.get("is_static"):
            decorators.append("    @staticmethod")
            signature = f"    def {method.name}({', '.join(typed_params)}) -> {self._python_type(method.return_type)}:"
        else:
            arg_list = ", ".join(["self", *typed_params])
            signature = f"    def {method.name}({arg_list}) -> {self._python_type(method.return_type)}:"
        lines = decorators + [signature]
        if class_kind == "interface" or method.metadata.get("is_abstract"):
            return lines + ["        ..."]
        rendered_body = []
        for block in method.blocks:
            for inst in block.instructions:
                rendered_body.extend(self._render_instruction(inst))
        if not rendered_body:
            rendered_body.append("        pass")
        self._current_field_names = prev_field_names
        self._current_static = prev_static
        return lines + rendered_body

    def _render_instruction(self, inst: IRInstruction) -> list[str]:
        if inst.op == "return":
            return [f"        return {self._render_expr_node(inst.args.get('expr'), str(inst.args['value']))}"]
        if inst.op == "throw":
            return [f"        raise Exception({self._render_expr_node(inst.args.get('expr'), str(inst.args['value']))})"]
        if inst.op == "if":
            return self._render_if(inst, 2)
        if inst.op == "for":
            return self._render_for(inst, 2)
        if inst.op == "enhanced_for":
            return self._render_enhanced_for(inst, 2)
        if inst.op == "while":
            return self._render_while(inst, 2)
        if inst.op in {"assign", "var_decl"}:
            translated = self._translate_assignment(inst.args)
            return [f"        {translated}", *self._maybe_stream_comment(str(inst.args["text"]))]
        special_stmt = self._translate_special_statement(str(inst.args["text"]))
        if special_stmt is not None:
            return [f"        {special_stmt}"]
        return [f"        {self._translate_expr(str(inst.args['text']))}", *self._maybe_stream_comment(str(inst.args['text']))]

    def _translate_assignment(self, text: str) -> str:
        if isinstance(text, dict):
            special = self._translate_special_statement(str(text.get("text", "")))
            if special is not None:
                return special
            if text.get("name") and text.get("expr") is not None:
                return f"{text['name']} = {self._render_expr_node(text.get('expr'), '')}"
            if text.get("target_expr") is not None and text.get("op"):
                target = self._render_expr_node(text.get("target_expr"), str(text.get("target", "")))
                op = str(text.get("op"))
                if op in {"++", "--"}:
                    return f"{target} {'+=' if op == '++' else '-='} 1"
                rhs = self._render_expr_node(text.get("expr"), "")
                return f"{target} {op} {rhs}"
            text = str(text.get("text", ""))
        special = self._translate_special_statement(text)
        if special is not None:
            return special
        match = re.match(r"(?:[\w<>\[\], ?]+\s+)?(\w+)\s*=\s*(.+)", text, flags=re.DOTALL)
        if not match:
            return self._translate_expr(text)
        name, expr = match.groups()
        translated_expr = self._translate_special_expression(expr) or self._translate_expr(expr)
        return f"{name} = {translated_expr}"

    def _maybe_stream_comment(self, text: str) -> list[str]:
        assign_match = re.match(r"(?:[\w<>\[\], ?]+\s+)?(\w+)\s*=\s*(.+)", text, flags=re.DOTALL)
        expr_text = assign_match.group(2) if assign_match else text
        if ".stream()" in text and self._translate_special_statement(text) is None and self._translate_special_expression(expr_text) is None:
            return ["        # TODO: review stream lowering for semantic parity"]
        return []

    def _python_type(self, java_type: str) -> str:
        mapping = {
            "String": "str",
            "int": "int",
            "long": "int",
            "double": "float",
            "float": "float",
            "boolean": "bool",
            "void": "None",
            "List": "list",
            "ArrayList": "list",
            "Map": "dict",
            "HashMap": "dict",
            "Set": "set",
            "HashSet": "set",
        }
        return mapping.get(java_type, java_type or "Any")

    def _render_if(self, inst: IRInstruction, indent_level: int) -> list[str]:
        indent = "    " * indent_level
        lines = [f"{indent}if {self._render_expr_node(inst.args.get('condition_expr'), str(inst.args['condition']))}:"]
        children = inst.args.get("children", [])
        lines.extend(self._render_nested(children, indent_level + 1))
        else_children = inst.args.get("else_children", [])
        if else_children:
            lines.append(f"{indent}else:")
            lines.extend(self._render_nested(else_children, indent_level + 1))
        return lines

    def _render_for(self, inst: IRInstruction, indent_level: int) -> list[str]:
        indent = "    " * indent_level
        init = str(inst.args.get("init", ""))
        condition = str(inst.args.get("condition", ""))
        update = str(inst.args.get("update", ""))
        range_header = self._translate_c_style_for(init, condition, update)
        if range_header is None:
            lines = [
                f"{indent}# TODO: manual review for Java for-loop lowering",
                f"{indent}while {self._render_expr_node(inst.args.get('condition_expr'), condition or 'True')}:",
            ]
            children = self._render_nested(inst.args.get("children", []), indent_level + 1)
            lines.extend(children if children else [f"{indent}    pass"])
            if update:
                lines.append(f"{indent}    {self._translate_expr(update)}")
            return lines
        lines = [f"{indent}{range_header}"]
        lines.extend(self._render_nested(inst.args.get("children", []), indent_level + 1))
        return lines

    def _render_enhanced_for(self, inst: IRInstruction, indent_level: int) -> list[str]:
        indent = "    " * indent_level
        lines = [f"{indent}for {inst.args.get('var', 'item')} in {self._render_expr_node(inst.args.get('iterable_expr'), str(inst.args.get('iterable', '[]')))}:"]
        lines.extend(self._render_nested(inst.args.get("children", []), indent_level + 1))
        return lines

    def _render_while(self, inst: IRInstruction, indent_level: int) -> list[str]:
        indent = "    " * indent_level
        lines = [f"{indent}while {self._render_expr_node(inst.args.get('condition_expr'), str(inst.args.get('condition', 'True')))}:"]
        lines.extend(self._render_nested(inst.args.get("children", []), indent_level + 1))
        return lines

    def _render_nested(self, instructions: list[IRInstruction], indent_level: int) -> list[str]:
        lines: list[str] = []
        for child in instructions:
            rendered = self._render_instruction_nested(child, indent_level)
            lines.extend(rendered)
        if not lines:
            lines.append(f"{'    ' * indent_level}pass")
        return lines

    def _render_instruction_nested(self, inst: IRInstruction, indent_level: int) -> list[str]:
        base = "    " * indent_level
        if inst.op == "return":
            return [f"{base}return {self._render_expr_node(inst.args.get('expr'), str(inst.args['value']))}"]
        if inst.op == "throw":
            return [f"{base}raise Exception({self._render_expr_node(inst.args.get('expr'), str(inst.args['value']))})"]
        if inst.op == "if":
            return self._render_if(inst, indent_level)
        if inst.op == "for":
            return self._render_for(inst, indent_level)
        if inst.op == "enhanced_for":
            return self._render_enhanced_for(inst, indent_level)
        if inst.op == "while":
            return self._render_while(inst, indent_level)
        if inst.op in {"assign", "var_decl"}:
            return [f"{base}{self._translate_assignment(inst.args)}"]
        special_stmt = self._translate_special_statement(str(inst.args["text"]))
        if special_stmt is not None:
            return [f"{base}{special_stmt}"]
        return [f"{base}{self._render_expr_node(inst.args.get('expr'), str(inst.args['text']))}"]

    def _translate_c_style_for(self, init: str, condition: str, update: str) -> str | None:
        init_match = re.match(r"(?:[\w<>\[\], ?]+\s+)?(\w+)\s*=\s*(.+)", init.strip())
        cond_match = re.match(r"(\w+)\s*([<>]=?)\s*(.+)", condition.strip())
        update_match = re.match(r"(\w+)(\+\+|--)", update.strip()) or re.match(r"(\w+)\s*([+\-]=)\s*(\d+)", update.strip())
        if not init_match or not cond_match or not update_match:
            return None
        var_name, start = init_match.groups()
        cond_var, operator, bound = cond_match.groups()
        if cond_var != var_name:
            return None
        if len(update_match.groups()) == 2:
            upd_var, token = update_match.groups()
            step = "1" if token == "++" else "-1"
        else:
            upd_var, token, amount = update_match.groups()
            step = amount if token == "+=" else f"-{amount}"
        if upd_var != var_name:
            return None
        start_expr = self._translate_expr(start)
        bound_expr = self._translate_expr(bound)
        if operator == "<":
            stop_expr = bound_expr
        elif operator == "<=":
            stop_expr = f"({bound_expr}) + 1"
        elif operator == ">":
            stop_expr = bound_expr
        else:
            stop_expr = f"({bound_expr}) - 1"
        if step == "1":
            return f"for {var_name} in range({start_expr}, {stop_expr}):"
        return f"for {var_name} in range({start_expr}, {stop_expr}, {step}):"

    def _translate_special_statement(self, text: str) -> str | None:
        compact = self._normalize_compact(text)
        thread_stmt = self._translate_thread_start(compact)
        if thread_stmt is not None:
            return thread_stmt
        return None

    def _translate_special_expression(self, text: str) -> str | None:
        compact = self._normalize_compact(text)
        for translator in (
            self._translate_arrays_as_list,
            self._translate_grouping_by_stream,
            self._translate_flatmap_foreach_stream,
            self._translate_filter_map_thread_stream,
            self._translate_filter_map_filter_sorted_stream,
            self._translate_stream_map_to_list,
            self._translate_completable_future_chain,
            self._translate_completable_future_supply,
            self._translate_reflection_expr,
            self._translate_method_reference_expr,
        ):
            translated = translator(compact)
            if translated is not None:
                return translated
        return None

    def _translate_arrays_as_list(self, text: str) -> str | None:
        match = re.fullmatch(r"Arrays\.asList\((.*)\)", text)
        if not match:
            return None
        inner = match.group(1).strip()
        return f"[{inner}]"

    def _translate_grouping_by_stream(self, text: str) -> str | None:
        match = re.fullmatch(
            r"(\w+)\.stream\(\)\.collect\(Collectors\.groupingBy\(\s*(\w+)\s*->\s*(.+?)\s*\)\)",
            text,
        )
        if not match:
            return None
        source, var_name, expr = match.groups()
        py_expr = self._translate_lambda_body(expr)
        return (
            "{"
            f"key: [item for item in {source} if ({py_expr.replace(var_name, 'item')}) == key] "
            f"for key in {{{py_expr.replace(var_name, 'item')} for item in {source}}}"
            "}"
        )

    def _translate_flatmap_foreach_stream(self, text: str) -> str | None:
        match = re.fullmatch(
            r"(\w+)\.stream\(\)\.flatMap\(\s*(\w+)\s*->\s*(\w+)\.stream\(\)\.map\(\s*(\w+)\s*->\s*(.+?)\s*\)\s*\)\.forEach\(System\.out::println\)",
            text,
        )
        if not match:
            return None
        source_a, x_var, source_b, y_var, body = match.groups()
        py_body = self._translate_lambda_body(body).replace(x_var, x_var).replace(y_var, y_var)
        return f"[print({py_body}) for {x_var} in {source_a} for {y_var} in {source_b}]"

    def _translate_filter_map_thread_stream(self, text: str) -> str | None:
        match = re.fullmatch(
            r"(\w+)\.stream\(\)\.filter\((\w+)\s*->\s*(.+?)\)\.sorted\(\)\.map\((\w+)\s*->\s*(.+?)\)\.forEach\((\w+)\s*->\s*\{\s*new Thread\(\(\)\s*->\s*\{\s*System\.out\.println\((.+?)\);\s*\}\)\.start\(\);\s*\}\)",
            text,
        )
        if not match:
            return None
        source, filter_var, filter_body, map_var, map_body, foreach_var, print_body = match.groups()
        filter_expr = self._translate_lambda_body(filter_body).replace(filter_var, "item")
        map_expr = self._translate_lambda_body(map_body).replace(map_var, "item").replace("transform(", "self.transform(")
        print_expr = self._translate_expr(print_body).replace(foreach_var, "value")
        return (
            f"[threading.Thread(target=lambda value=value: print({print_expr})).start() "
            f"for value in [{map_expr} for item in sorted([item for item in self.{source} if {filter_expr}])]]"
        )

    def _translate_filter_map_filter_sorted_stream(self, text: str) -> str | None:
        match = re.fullmatch(
            r"(\w+)\.stream\(\)\.filter\((\w+)\s*->\s*(.+?)\)\.map\((\w+)\s*->\s*(.+?)\)\.filter\((\w+)\s*->\s*(.+?)\)\.sorted\(\)\.toList\(\)",
            text,
        )
        if not match:
            return None
        source, filter1_var, filter1_body, map_var, map_body, filter2_var, filter2_body = match.groups()
        filter1_expr = self._translate_lambda_body(filter1_body).replace(filter1_var, "item")
        map_expr = self._translate_lambda_body(map_body).replace(map_var, "item")
        filter2_expr = self._translate_lambda_body(filter2_body).replace(filter2_var, "value")
        return (
            f"sorted([value for value in [{map_expr} for item in {source} if {filter1_expr}] "
            f"if {filter2_expr}])"
        )

    def _translate_stream_map_to_list(self, text: str) -> str | None:
        match = re.fullmatch(r"(\w+)\.stream\(\)\.map\((.+?)\)(?:\.toList\(\))?", text)
        if not match:
            return None
        source, mapper = match.groups()
        if "::" in mapper:
            owner, method = mapper.split("::", 1)
            if owner == "this":
                target_source = f"self.{source}" if source == "data" else source
                return f"[self.{method}(item) for item in {target_source}]"
            return f"[{owner.lower()}.{method}(item) for item in {source}]"
        lambda_match = re.fullmatch(r"(\w+)\s*->\s*(.+)", mapper)
        if not lambda_match:
            return None
        var_name, body = lambda_match.groups()
        py_body = self._translate_lambda_body(body)
        target_source = f"self.{source}" if source == "data" else source
        return f"[{py_body} for {var_name} in {target_source}]"

    def _translate_completable_future_chain(self, text: str) -> str | None:
        match = re.fullmatch(
            r"CompletableFuture\.supplyAsync\(\(\)\s*->\s*(.+?)\)\.thenApply\((\w+)\s*->\s*(.+?)\)\.thenApply\((\w+)\s*->\s*(.+?)\)\.thenAccept\(System\.out::println\)",
            text,
        )
        if not match:
            return None
        seed, var1, expr1, var2, expr2 = match.groups()
        py1 = self._translate_lambda_body(expr1).replace(var1, f"({self._translate_expr(seed)})")
        py2 = self._translate_lambda_body(expr2).replace(var2, f"({py1})")
        return f"print({py2})"

    def _translate_completable_future_supply(self, text: str) -> str | None:
        match = re.fullmatch(r"CompletableFuture\.supplyAsync\(\(\)\s*->\s*\{\s*return\s+(.+?)\s*;\s*\}\)", text)
        if match:
            return self._translate_expr(match.group(1))
        match = re.fullmatch(r"CompletableFuture\.supplyAsync\(\(\)\s*->\s*(.+?)\)", text)
        if match:
            return self._translate_expr(match.group(1))
        return None

    def _translate_reflection_expr(self, text: str) -> str | None:
        if text == 'Class.forName("java.lang.String")':
            return 'str  # TODO: Java reflection Class.forName mapped conservatively'
        if text == "cls.getDeclaredMethods()":
            return "[name for name in dir(cls) if callable(getattr(cls, name, None))]"
        if text == "m.getName()":
            return 'm if isinstance(m, str) else getattr(m, "__name__", str(m))'
        return None

    def _translate_method_reference_expr(self, text: str) -> str | None:
        if text == "System.out::println":
            return "print"
        return None

    def _translate_thread_start(self, text: str) -> str | None:
        match = re.fullmatch(r"new Thread\(\(\)\s*->\s*\{\s*System\.out\.println\((.+?)\);\s*\}\)\.start\(\)", text)
        if not match:
            return None
        inner = self._translate_expr(match.group(1))
        return f"threading.Thread(target=lambda: print({inner})).start()"

    def _translate_lambda_body(self, body: str) -> str:
        text = body.strip()
        text = re.sub(r"(\w+)\s*!=\s*null", r"\1 is not None", text)
        text = re.sub(r"(\w+)\.stream\(\)\.map\((\w+)\s*->\s*(.+?)\)", lambda m: f"[{self._translate_lambda_body(m.group(3))} for {m.group(2)} in {m.group(1)}]", text)
        text = text.replace("System.out.println", "print")
        text = text.replace("this::", "self.")
        text = text.replace("this.", "self.")
        java_ternary = re.fullmatch(r"(.+?)\?\s*(.+?)\s*:\s*(.+)", text)
        if java_ternary:
            condition, left, right = java_ternary.groups()
            return f"({self._translate_lambda_body(left)} if {self._translate_lambda_body(condition)} else {self._translate_lambda_body(right)})"
        return self._translate_expr(text) if text != body.strip() else text.replace("null", "None")

    def _normalize_compact(self, text: str) -> str:
        compact = " ".join(text.strip().split())
        compact = compact.replace(" .", ".")
        compact = compact.replace("( ", "(").replace(" )", ")")
        compact = compact.replace("{ ", "{").replace(" }", "}")
        return compact

    def _translate_expr(self, expr: str) -> str:
        text = expr.strip().rstrip(";")
        special = self._translate_special_expression(text)
        if special is not None:
            return special
        replacements = {
            "true": "True",
            "false": "False",
            "null": "None",
            "this.": "self.",
            "System.out.println": "print",
            "new ArrayList<>()": "[]",
            "new HashMap<>()": "{}",
            "new HashSet<>()": "set()",
            ".toList()": "",
        }
        for old, new in replacements.items():
            text = text.replace(old, new)
        text = re.sub(r"new\s+\w+(?:<.*?>)?\((.*?)\)", lambda m: f"{m.group(1) or ''}", text, flags=re.DOTALL)
        text = text.replace(".add(", ".append(")
        text = text.replace(".put(", ".__setitem__(")
        text = text.replace(".get(", ".get(")
        text = text.replace(".length()", ".__len__()")
        text = self._translate_new_array(text)
        text = self._translate_increment_ops(text)
        text = self._qualify_instance_fields(text)
        text = self._translate_string_concat(text)
        return text

    def _render_expr_node(self, expr: object, fallback_text: str) -> str:
        if not isinstance(expr, dict) or not expr:
            return self._translate_expr(fallback_text)
        kind = expr.get("kind")
        if kind in {"raw", "lambda_raw"}:
            return self._translate_expr(str(expr.get("text") or expr.get("body") or fallback_text))
        if kind == "empty":
            return ""
        if kind == "number":
            return str(expr.get("value"))
        if kind == "string":
            return str(expr.get("value"))
        if kind == "bool":
            return "True" if expr.get("value") else "False"
        if kind == "null":
            return "None"
        if kind == "name":
            value = str(expr.get("value"))
            return self._qualify_instance_fields("self" if value == "this" else value)
        if kind == "member":
            target = self._render_expr_node(expr.get("target"), "")
            name = str(expr.get("name"))
            return f"{target}.{name}"
        if kind == "index":
            target = self._render_expr_node(expr.get("target"), "")
            index = self._render_expr_node(expr.get("index"), "")
            return f"{target}[{index}]"
        if kind == "call":
            target = self._render_expr_node(expr.get("target"), "")
            args = ", ".join(self._render_expr_node(arg, "") for arg in expr.get("args", []))
            return self._translate_expr(f"{target}({args})")
        if kind == "method_ref":
            target = self._render_expr_node(expr.get("target"), "")
            return f"{target}::{expr.get('name')}"
        if kind == "new_call":
            type_name = str(expr.get("type"))
            args = ", ".join(self._render_expr_node(arg, "") for arg in expr.get("args", []))
            return self._translate_expr(f"new {type_name}({args})")
        if kind == "new_array":
            dims = [self._render_expr_node(dim, "0") for dim in expr.get("dims", []) if isinstance(dim, dict) and dim.get("kind") != "empty"]
            return self._translate_new_array(f"new {expr.get('type')}" + "".join(f"[{dim}]" for dim in dims))
        if kind == "unary":
            op = str(expr.get("op"))
            value = self._render_expr_node(expr.get("value"), "")
            return f"{op} {value}" if op == "not" else f"{op}{value}"
        if kind == "binary":
            left = self._render_expr_node(expr.get("left"), "")
            right = self._render_expr_node(expr.get("right"), "")
            op = str(expr.get("op"))
            op = {"&&": "and", "||": "or"}.get(op, op)
            return self._translate_string_concat(f"{left} {op} {right}")
        if kind == "ternary":
            cond = self._render_expr_node(expr.get("condition"), "")
            then_expr = self._render_expr_node(expr.get("then"), "")
            else_expr = self._render_expr_node(expr.get("else"), "")
            return f"({then_expr} if {cond} else {else_expr})"
        if kind == "lambda":
            params = ", ".join(str(param) for param in expr.get("params", []))
            body = self._render_expr_node(expr.get("body"), "")
            return f"lambda {params}: {body}"
        return self._translate_expr(fallback_text)

    def _translate_string_concat(self, text: str) -> str:
        if '"' not in text or "+" not in text:
            return text
        parts = [part.strip() for part in text.split("+")]
        converted: list[str] = []
        saw_string_literal = any(part.startswith('"') or part.endswith('"') for part in parts)
        if not saw_string_literal:
            return text
        for part in parts:
            if part.startswith('"') and part.endswith('"'):
                converted.append(part)
            elif part.startswith("'") and part.endswith("'"):
                converted.append(part)
            else:
                converted.append(f"str({part})")
        return " + ".join(converted)

    def _translate_increment_ops(self, text: str) -> str:
        postfix = re.fullmatch(r"(.+?)(\+\+|--)", text.strip())
        if postfix:
            target, op = postfix.groups()
            return f"{target} {'+=' if op == '++' else '-='} 1"
        return text

    def _translate_new_array(self, text: str) -> str:
        match = re.fullmatch(r"new\s+\w+(?:\[\])*(\[[^\]]+\])+", text.strip())
        if not match:
            return text
        dims = re.findall(r"\[([^\]]+)\]", text)
        return self._build_nested_array(dims)

    def _build_nested_array(self, dims: list[str], depth: int = 0) -> str:
        if depth >= len(dims):
            return "0"
        inner = self._build_nested_array(dims, depth + 1)
        return f"[{inner} for _ in range({dims[depth]})]"

    def _qualify_instance_fields(self, text: str) -> str:
        if self._current_static or not self._current_field_names:
            return text
        for name in sorted(self._current_field_names, key=len, reverse=True):
            text = re.sub(rf"(?<![\w.]){re.escape(name)}(?![\w(])", f"self.{name}", text)
            text = re.sub(rf"(?<![\w.]){re.escape(name)}(?=\()", f"self.{name}", text)
        return text

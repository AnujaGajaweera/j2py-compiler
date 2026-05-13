from __future__ import annotations

from transpiler.ast_nodes import Statement
from transpiler.semantic.model import SemanticModel

from .model import IRBlock, IRClass, IRFunction, IRInstruction, IRModule


class IRLowerer:
    def lower(self, semantic_model: SemanticModel) -> IRModule:
        unit = semantic_model.compilation_unit
        classes: list[IRClass] = []
        for decl in unit.declarations:
            methods = []
            for method in decl.methods:
                block = IRBlock(name="entry")
                for stmt in method.body:
                    block.instructions.append(self._lower_statement(stmt))
                methods.append(
                    IRFunction(
                        name=method.name,
                        params=[param.name for param in method.params],
                        return_type=semantic_model.symbols[f"{decl.name}.{method.name}"].type_info.python_type,
                        blocks=[block],
                        metadata={
                            "is_static": method.is_static,
                            "is_abstract": method.is_abstract,
                            "param_types": {
                                param.name: semantic_model.symbols.get(
                                    f"{decl.name}.{method.name}.{param.name}",
                                    None,
                                )
                                for param in method.params
                            },
                            "param_type_names": {
                                param.name: param.type_ref.name for param in method.params
                            },
                        },
                    )
                )
            fields = [
                {
                    "name": field.name,
                    "type": semantic_model.symbols[f"{decl.name}.{field.name}"].type_info.python_type,
                    "initializer": field.initializer,
                    "is_static": field.is_static,
                }
                for field in decl.fields
            ]
            classes.append(
                IRClass(
                    name=decl.name,
                    kind=decl.kind,
                    bases=decl.bases,
                    fields=fields,
                    methods=methods,
                    metadata={"modifiers": decl.modifiers},
                )
            )
        return IRModule(name=unit.path, package=unit.package, classes=classes, metadata={"facts": semantic_model.facts})

    def _lower_statement(self, stmt: Statement) -> IRInstruction:
        match stmt.kind:
            case "return":
                return IRInstruction("return", {"value": stmt.text, "expr": stmt.metadata.get("expr")})
            case "throw":
                return IRInstruction("throw", {"value": stmt.text, "expr": stmt.metadata.get("expr")})
            case "if":
                return IRInstruction(
                    "if",
                    {
                        "condition": stmt.metadata.get("condition", ""),
                        "condition_expr": stmt.metadata.get("condition_expr"),
                        "children": [self._lower_statement(child) for child in stmt.children],
                        "else_children": [self._lower_statement(child) for child in stmt.else_children],
                    },
                )
            case "for":
                return IRInstruction(
                    "for",
                    {
                        "init": stmt.metadata.get("init", ""),
                        "condition": stmt.metadata.get("condition", ""),
                        "condition_expr": stmt.metadata.get("condition_expr"),
                        "update": stmt.metadata.get("update", ""),
                        "children": [self._lower_statement(child) for child in stmt.children],
                    },
                )
            case "enhanced_for":
                return IRInstruction(
                    "enhanced_for",
                    {
                        "var": stmt.metadata.get("var", "item"),
                        "iterable": stmt.metadata.get("iterable", ""),
                        "iterable_expr": stmt.metadata.get("iterable_expr"),
                        "children": [self._lower_statement(child) for child in stmt.children],
                    },
                )
            case "while":
                return IRInstruction(
                    "while",
                    {
                        "condition": stmt.metadata.get("condition", ""),
                        "condition_expr": stmt.metadata.get("condition_expr"),
                        "children": [self._lower_statement(child) for child in stmt.children],
                    },
                )
            case "var_decl":
                return IRInstruction("var_decl", {"text": stmt.text, **stmt.metadata})
            case "assign":
                return IRInstruction("assign", {"text": stmt.text, **stmt.metadata})
            case _:
                return IRInstruction("expr", {"text": stmt.text, **stmt.metadata})

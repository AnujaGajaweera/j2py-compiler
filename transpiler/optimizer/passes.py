from __future__ import annotations

import re
from dataclasses import dataclass, field

from transpiler.ir.model import IRInstruction, IRModule


class OptimizationPass:
    name = "optimization-pass"

    def run(self, module: IRModule) -> IRModule:
        raise NotImplementedError


class ConstantFoldingPass(OptimizationPass):
    name = "constant-folding"

    def run(self, module: IRModule) -> IRModule:
        for ir_class in module.classes:
            for method in ir_class.methods:
                for block in method.blocks:
                    for inst in block.instructions:
                        if inst.op in {"assign", "var_decl"} and isinstance(inst.args.get("text"), str):
                            inst.args["text"] = _fold_constant_expression(inst.args["text"])
        return module


class RedundantTemporaryPass(OptimizationPass):
    name = "redundant-temporary"

    def run(self, module: IRModule) -> IRModule:
        for ir_class in module.classes:
            for method in ir_class.methods:
                for block in method.blocks:
                    block.instructions = [
                        inst for inst in block.instructions if not (inst.op == "expr" and inst.args.get("text") == "")
                    ]
        return module


@dataclass(slots=True)
class PassManager:
    passes: list[OptimizationPass] = field(default_factory=lambda: [ConstantFoldingPass(), RedundantTemporaryPass()])

    def run(self, module: IRModule) -> IRModule:
        for opt_pass in self.passes:
            module = opt_pass.run(module)
        return module


def _fold_constant_expression(text: str) -> str:
    match = re.match(r"(.+?)=\s*(\d+)\s*([+*-])\s*(\d+)$", text.strip())
    if not match:
        return text
    lhs, left, op, right = match.groups()
    a = int(left)
    b = int(right)
    value = a + b if op == "+" else a - b if op == "-" else a * b
    return f"{lhs}= {value}"


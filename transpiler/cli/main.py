from __future__ import annotations

import argparse
import json
from pathlib import Path

from transpiler.pipeline import CompilerPipeline, CompilerSettings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="j2py", description="Java-to-Python compiler scaffold")
    subparsers = parser.add_subparsers(dest="command", required=True)

    compile_parser = subparsers.add_parser("compile")
    compile_parser.add_argument("target")
    compile_parser.add_argument("--out", default="out")

    analyze_parser = subparsers.add_parser("analyze")
    analyze_parser.add_argument("target")

    inspect_parser = subparsers.add_parser("inspect-ir")
    inspect_parser.add_argument("target")

    report_parser = subparsers.add_parser("report")
    report_parser.add_argument("target")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "compile":
        pipeline = CompilerPipeline(CompilerSettings(output_dir=Path(args.out)))
        result = pipeline.compile(args.target)
        print(json.dumps(_result_to_json(result), indent=2))
        return 0 if not any(item.severity.value == "error" for item in result.diagnostics) else 1
    if args.command == "analyze":
        pipeline = CompilerPipeline()
        result = pipeline.analyze(args.target)
        print(json.dumps(_result_to_json(result), indent=2))
        return 0
    if args.command == "inspect-ir":
        pipeline = CompilerPipeline()
        print(json.dumps(pipeline.inspect_ir(args.target), indent=2))
        return 0
    if args.command == "report":
        pipeline = CompilerPipeline()
        result = pipeline.analyze(args.target)
        print(json.dumps(result.reports, indent=2))
        return 0
    return 1


def _result_to_json(result) -> dict[str, object]:
    return {
        "root": str(result.project.root),
        "sources": [str(source.path) for source in result.project.sources],
        "emitted_files": [str(path) for path in result.emitted_files],
        "diagnostics": [
            {
                "code": item.code,
                "severity": item.severity.value,
                "message": item.message,
                "category": item.category,
                "fallback": item.fallback,
            }
            for item in result.diagnostics
        ],
        "reports": result.reports,
    }


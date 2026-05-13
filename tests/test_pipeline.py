from __future__ import annotations

import json
import py_compile
import tempfile
import unittest
from pathlib import Path

from transpiler.pipeline import CompilerPipeline, CompilerSettings


class PipelineTests(unittest.TestCase):
    def test_compile_example_emits_python(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pipeline = CompilerPipeline(CompilerSettings(output_dir=Path(tmp)))
            result = pipeline.compile("examples/Main.java")
            self.assertFalse(any(item.severity.value == "error" for item in result.diagnostics))
            generated = Path(tmp) / "Main.py"
            self.assertTrue(generated.exists())
            content = generated.read_text(encoding="utf-8")
            self.assertIn("class Main", content)
            self.assertIn("BasicMath.main(args)", content)

    def test_inspect_ir_returns_module(self) -> None:
        pipeline = CompilerPipeline()
        ir_dump = pipeline.inspect_ir("examples/core/BasicMath.java")
        self.assertIn(str(Path("examples/core/BasicMath.java").resolve()), ir_dump)
        module = ir_dump[str(Path("examples/core/BasicMath.java").resolve())]
        self.assertEqual(module["package"], "core")

    def test_report_contains_framework_facts(self) -> None:
        pipeline = CompilerPipeline()
        result = pipeline.analyze("examples/Main.java")
        report = result.reports[str(Path("examples/Main.java").resolve())]
        self.assertIn("facts", report)

    def test_control_flow_emits_python_loops(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pipeline = CompilerPipeline(CompilerSettings(output_dir=Path(tmp)))
            result = pipeline.compile("examples/core/ControlFlowHell.java")
            self.assertFalse(any(item.severity.value == "error" for item in result.diagnostics))
            generated = Path(tmp) / "core" / "ControlFlowHell.py"
            content = generated.read_text(encoding="utf-8")
            self.assertIn("for i in range", content)
            self.assertIn("if i % 2 == 0", content)

    def test_reflection_and_backend_patterns_are_reported(self) -> None:
        pipeline = CompilerPipeline()
        result = pipeline.analyze("examples")
        reflection_report = result.reports[str(Path("examples/reflection/ReflectionBomb.java").resolve())]
        backend_report = result.reports[str(Path("examples/backend/ApiController.java").resolve())]
        self.assertTrue(reflection_report["facts"]["uses_reflection"])
        self.assertIn("controller", backend_report["frameworks"])

    def test_threadstorm_uses_threading(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pipeline = CompilerPipeline(CompilerSettings(output_dir=Path(tmp)))
            pipeline.compile("examples/concurrency/ThreadStorm.java")
            content = (Path(tmp) / "concurrency" / "ThreadStorm.py").read_text(encoding="utf-8")
            self.assertIn("import threading", content)
            self.assertIn("threading.Thread(", content)

    def test_stream_collector_lowers_to_native_python(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pipeline = CompilerPipeline(CompilerSettings(output_dir=Path(tmp)))
            pipeline.compile("examples/streams/CollectorChaos.java")
            content = (Path(tmp) / "streams" / "CollectorChaos.py").read_text(encoding="utf-8")
            self.assertIn("grouped = {key:", content)
            self.assertNotIn("TODO: review stream lowering", content)

    def test_stress_example_recovers_mixed_pipeline_structure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pipeline = CompilerPipeline(CompilerSettings(output_dir=Path(tmp)))
            pipeline.compile("examples/mixed/UltimateStressTest.java")
            content = (Path(tmp) / "mixed" / "UltimateStressTest.py").read_text(encoding="utf-8")
            self.assertIn("self.data", content)
            self.assertIn("threading.Thread(", content)
            self.assertIn("self.transform(item)", content)

    def test_engine_and_counter_outputs_are_python_compilable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pipeline = CompilerPipeline(CompilerSettings(output_dir=Path(tmp)))
            pipeline.compile("examples/engine/ChunkEngine.java")
            pipeline.compile("examples/engine/EntitySystem.java")
            pipeline.compile("examples/concurrency/SynchronizedCounter.java")
            for relpath in (
                ("engine", "ChunkEngine.py"),
                ("engine", "EntitySystem.py"),
                ("concurrency", "SynchronizedCounter.py"),
            ):
                py_compile.compile(str(Path(tmp).joinpath(*relpath)), doraise=True)

    def test_stream_overload_lowers_to_sorted_native_pipeline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pipeline = CompilerPipeline(CompilerSettings(output_dir=Path(tmp)))
            pipeline.compile("examples/streams/StreamOverload.java")
            content = (Path(tmp) / "streams" / "StreamOverload.py").read_text(encoding="utf-8")
            self.assertIn("result = sorted(", content)
            self.assertNotIn(".stream()", content)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from transpiler.build.discovery import discover_project


class DiscoveryTests(unittest.TestCase):
    def test_discovers_single_file(self) -> None:
        project = discover_project("examples/Main.java")
        self.assertEqual(len(project.sources), 1)
        self.assertEqual(project.sources[0].kind, "java")

    def test_discovers_gradle_layout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "build.gradle").write_text("plugins {}", encoding="utf-8")
            src = root / "src" / "main" / "java"
            src.mkdir(parents=True)
            (src / "App.java").write_text("class App {}", encoding="utf-8")
            project = discover_project(root)
            self.assertEqual(project.metadata["build_system"], "gradle")
            self.assertEqual(len(project.sources), 1)


if __name__ == "__main__":
    unittest.main()

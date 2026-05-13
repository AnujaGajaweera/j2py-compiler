# j2py-compiler

`j2py-compiler` is a compiler-style Java-to-Python transpiler scaffold designed around a real pipeline:

```text
Java Source / Bytecode
  -> frontend
  -> semantic analysis
  -> typed semantic graph
  -> typed IR
  -> optimization passes
  -> Python backend
```

This project is intentionally closer to a compiler architecture like GraalVM, Jython, Eclipse JDT, or Cython than to a text-level source converter.

## Current state

This repository is a production-oriented foundation with a working vertical slice:

- source project discovery for single files, directories, Maven, and Gradle layouts
- JDT bridge contract with environment-based activation
- pure-Python fallback source frontend for a useful Java subset
- bytecode/class analysis through `javap`
- semantic model, diagnostics, typed IR, optimizer pass manager
- Python backend that emits standard-library-only Python
- plugin interfaces and built-in framework detectors
- CLI commands for compile, analyze, inspect-ir, and report
- unittest coverage for the end-to-end slice

## Architecture direction

The intended long-term pipeline is:

```text
Java Source / .class / .jar
  -> Java frontend
  -> normalized AST
  -> semantic analysis
  -> typed symbol graph
  -> language-neutral IR
  -> optimization passes
  -> Python backend
```

Key design rules:

- no direct Java-source-to-Python-source conversion
- semantic analysis before lowering
- IR as the stable boundary between frontend and backend
- pure Python standard-library output by default
- unsupported JVM semantics surfaced as diagnostics, not hidden runtime emulation

## JDT bridge

Set `J2PY_JDT_JAR` to an Eclipse JDT core jar to enable the Java bridge frontend:

```powershell
$env:J2PY_JDT_JAR="C:\path\to\org.eclipse.jdt.core.jar"
```

If the jar is not configured, the compiler falls back to the built-in subset frontend and emits a diagnostic explaining the downgrade.

## CLI

```powershell
python -m transpiler compile examples\Main.java --out out
python -m transpiler analyze examples
python -m transpiler inspect-ir examples\core\BasicMath.java
python -m transpiler report examples
```

## Architecture

- `transpiler/frontend`: source and bytecode frontends
- `transpiler/semantic`: symbol and dependency analysis
- `transpiler/ir`: typed intermediate representation
- `transpiler/optimizer`: optimization passes
- `transpiler/backend/python`: Python emitter
- `transpiler/build`: project discovery and incremental cache helpers
- `transpiler/plugins`: plugin interfaces and detectors
- `transpiler/cli`: command entrypoints

## Development order

### Phase 1

- classes
- methods
- variables
- loops
- conditionals

### Phase 2

- inheritance
- interfaces
- generics
- collections

### Phase 3

- threading
- streams
- lambdas
- annotations

### Phase 4

- reflection
- bytecode analysis
- optimization

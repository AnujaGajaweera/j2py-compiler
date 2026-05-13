# Architecture Notes

## Design goals

- pure-Python generated output
- no Java compatibility runtime
- typed IR between frontend and backend
- graceful degradation on unsupported JVM features
- plugin-ready structure for framework and graphics rewrites
- compiler-first architecture rather than direct source rewriting

## Compiler model

This project should be treated as a compiler pipeline, not a syntax converter:

```text
Java Source / Bytecode
  -> Java frontend
  -> normalized AST
  -> semantic analysis
  -> typed symbol graph
  -> IR
  -> optimization
  -> Python backend
```

The important consequence is that each stage has a specific job:

- frontend:
  parse Java into a normalized internal AST using a real parser
- semantic analysis:
  resolve symbols, types, imports, inheritance, overloads, generics, visibility, and feature usage
- IR:
  preserve meaning in a backend-neutral form
- backend:
  emit readable Python from IR, not from raw Java text

## Current implementation slice

The repository currently ships a working vertical slice for:

- Java source discovery
- source parsing with JDT bridge contract and fallback subset parser
- bytecode inspection through `javap`
- semantic facts and symbol graph creation
- IR lowering and lightweight optimization
- Python code generation and JSON reporting

## Hard-problem areas

The roadmap assumes several problem classes require dedicated handling instead of ad hoc rewrites:

- method overloading:
  dispatcher generation or name-mangled lowering
- generics:
  typing-aware lowering with conservative runtime semantics
- streams:
  AST/IR-level transformation into comprehensions, loops, and functional pipelines
- concurrency:
  explicit policy for `Thread`, `synchronized`, `volatile`, and `CompletableFuture`
- reflection:
  diagnostics-first handling with conservative rewrites where possible
- bytecode-dependent behavior:
  classify and report unsupported JVM-specific assumptions

## Domain notes

- game-engine style code:
  expect rendering, native bindings, packed data structures, and hot loops to need specialized lowering or manual intervention
- backend/microservice code:
  expect framework adapters and concurrency-policy decisions rather than naive translation
- performance-sensitive code:
  plan for later optional strategies such as PyPy or Cython-oriented backend modes, while keeping the default output pure standard-library Python

## Intended next steps

- replace fallback subset parser coverage with JDT bridge normalization
- deepen method-body representation from heuristic strings toward real expression trees
- add control-flow graph reconstruction for bytecode
- improve overload dispatch and generics lowering
- make concurrency and stream lowering more principled and less pattern-based
- add formatter/lint integration and richer unsupported-feature handling

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class FrontendPlugin:
    name: str


@dataclass(slots=True)
class SemanticRulePlugin:
    name: str


@dataclass(slots=True)
class IRPassPlugin:
    name: str


@dataclass(slots=True)
class BackendRewritePlugin:
    name: str


@dataclass(slots=True)
class FrameworkAdapterPlugin:
    name: str


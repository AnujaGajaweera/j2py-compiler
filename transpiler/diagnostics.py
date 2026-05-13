from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass(slots=True)
class SourceSpan:
    path: str
    line: int = 0
    column: int = 0


@dataclass(slots=True)
class Diagnostic:
    code: str
    message: str
    severity: Severity
    span: SourceSpan | None = None
    fallback: str | None = None
    category: str = "general"


@dataclass(slots=True)
class DiagnosticBag:
    items: list[Diagnostic] = field(default_factory=list)

    def add(
        self,
        code: str,
        message: str,
        severity: Severity = Severity.ERROR,
        span: SourceSpan | None = None,
        fallback: str | None = None,
        category: str = "general",
    ) -> None:
        self.items.append(
            Diagnostic(
                code=code,
                message=message,
                severity=severity,
                span=span,
                fallback=fallback,
                category=category,
            )
        )

    def extend(self, diagnostics: list[Diagnostic]) -> None:
        self.items.extend(diagnostics)

    @property
    def has_errors(self) -> bool:
        return any(item.severity == Severity.ERROR for item in self.items)


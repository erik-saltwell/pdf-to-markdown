"""Small, stdlib-only result types shared by the CLI and isolated workers."""

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class Diagnostic:
    message: str
    source: str
    page: int | None = None
    severity: str = "warning"


@dataclass
class Extraction:
    markdown: str
    pages: list[int]
    images: int = 0
    warnings: list[Diagnostic] = field(default_factory=list)
    filtered_images: list[dict[str, Any]] = field(default_factory=list)
    native_report: str | None = None
    native_artifacts: list[str] = field(default_factory=list)
    options: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ConversionError(RuntimeError):
    """A run cannot be published, regardless of how much text was extracted."""


class ArgumentError(ValueError):
    """A path or command argument cannot describe a safe conversion request."""

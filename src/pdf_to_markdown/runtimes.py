"""Discover the four independently locked local conversion environments."""

import hashlib
import json
import os
from pathlib import Path

from pdf_to_markdown.settings import Converter

REQUIREMENTS = Path(__file__).parent / "runtime_requirements"


def runtime_root() -> Path:
    data = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    return data / "pdf-to-markdown" / "runtimes"


def lock_path(converter: str) -> Path:
    return REQUIREMENTS / f"{converter}-linux-py312.txt"


def lock_digest(converter: str) -> str:
    return hashlib.sha256(lock_path(converter).read_bytes()).hexdigest()


def runtime_python(converter: Converter) -> Path:
    """Require a complete installation matching this application's locks."""
    try:
        registry = json.loads((runtime_root() / "registry.json").read_text())
        for backend in Converter:
            entry = registry[backend.value]
            if entry["lock_sha256"] != lock_digest(backend.value):
                raise ValueError(f"The {backend} runtime needs updating.")
            if not Path(entry["python"]).is_file():
                raise ValueError(f"The {backend} runtime is missing.")
        return Path(registry[converter.value]["python"])
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise RuntimeError(
            "Converter runtimes are not installed or are outdated. "
            "Run scripts/install-tool.sh from the checkout to install all four."
        ) from exc

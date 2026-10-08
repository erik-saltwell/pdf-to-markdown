"""One-operation setup of every backend; invoked by scripts/install-tool.sh."""

import json
import os
import platform
import shutil
import subprocess
import sys
import uuid

from pdf_to_markdown.runtimes import lock_digest, lock_path, runtime_root
from pdf_to_markdown.settings import Converter

IMPORTS = {
    "docling": "docling.document_converter",
    "marker": "marker.converters.pdf",
    "pymupdf4llm": "pymupdf4llm",
    "mineru": "mineru.parser",
}


def main() -> None:
    """Provision all workers before atomically activating their registry."""
    if sys.platform != "linux" or platform.machine() not in {"x86_64", "AMD64"}:
        raise SystemExit(
            "The supplied runtime locks support Linux x86_64 / Python 3.12."
        )
    uv = shutil.which("uv")
    if uv is None:
        raise SystemExit("Install uv before running setup.")
    root = runtime_root()
    root.mkdir(parents=True, exist_ok=True)
    registry = {}
    for backend in Converter:
        digest = lock_digest(backend.value)
        environment = root / f"{backend}-{digest[:16]}"
        python = environment / "bin/python"
        print(f"Installing {backend} runtime…", flush=True)
        if not python.exists():
            subprocess.run(
                [uv, "venv", "--python", "3.12", str(environment)], check=True
            )
        subprocess.run(
            [
                uv,
                "pip",
                "sync",
                "--python",
                str(python),
                "--require-hashes",
                str(lock_path(backend.value)),
            ],
            check=True,
        )
        subprocess.run([uv, "pip", "check", "--python", str(python)], check=True)
        subprocess.run(
            [
                str(python),
                "-c",
                "import importlib; "
                f"importlib.import_module({IMPORTS[backend.value]!r}); "
                "import pymupdf, PIL, markdown_it",
            ],
            check=True,
        )
        registry[backend.value] = {"python": str(python), "lock_sha256": digest}
    temporary = root / f".registry-{uuid.uuid4().hex}.json"
    try:
        with temporary.open("x") as stream:
            json.dump(registry, stream, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(root / "registry.json")
    finally:
        temporary.unlink(missing_ok=True)
    print("All four converter runtimes are ready. Models download on first use.")


if __name__ == "__main__":
    main()

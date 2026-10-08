"""Run one converter in its isolated interpreter and write a validated result."""

import hashlib
import importlib
import importlib.metadata
import json
import logging
import os
import re
import sys
import traceback
import warnings
from pathlib import Path
from typing import Any

from pdf_to_markdown.assets import image_file, image_references
from pdf_to_markdown.contracts import ConversionError, Diagnostic

DISTRIBUTIONS = {
    "docling": "docling",
    "marker": "marker-pdf",
    "pymupdf4llm": "pymupdf4llm",
    "mineru": "mineru",
}


class WarningLog(logging.Handler):
    def __init__(self) -> None:
        super().__init__(logging.WARNING)
        self.diagnostics: list[Diagnostic] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.diagnostics.append(
            Diagnostic(
                record.getMessage(),
                record.name,
                severity="error" if record.levelno >= logging.ERROR else "warning",
            )
        )


def local_environment(converter: str) -> Path:
    cache = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    root = cache / "pdf-to-markdown" / "models" / converter
    root.mkdir(parents=True, exist_ok=True)
    os.environ["HF_HOME"] = str(root / "huggingface")
    os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "0"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    os.environ["TORCH_HOME"] = str(root / "torch")
    # Adapters instantiate only local engines; inherited remote options are removed.
    for key in list(os.environ):
        if key.startswith(("SURYA_INFERENCE_", "MINERU_", "DOCLING_")):
            os.environ.pop(key)
    if converter == "mineru":
        os.environ["MINERU_HOME"] = str(root / "mineru")
        os.environ["MINERU_MODEL_SMALL_BACKEND"] = "onnx"
    return root


def run(request: dict[str, Any]) -> dict[str, Any]:
    converter = request["converter"]
    if converter not in DISTRIBUTIONS:
        raise ConversionError("Unknown worker converter.")
    source = Path(request["source"])
    stage = Path(request["stage"])
    cache = local_environment(converter)
    pdf_module = importlib.import_module("pymupdf")
    with pdf_module.open(source) as pdf:
        if not pdf.is_pdf or pdf.needs_pass or pdf.page_count < 1:
            raise ConversionError(
                "Input must be a readable, unencrypted, nonempty PDF."
            )
        expected = list(range(1, pdf.page_count + 1))
        for page in pdf:
            page.get_text(
                "text"
            )  # Preflight every physical page, without quality scoring.
    if request.get("operation") == "inspect":
        return {"success": True, "pages": expected}
    adapter = importlib.import_module(f"pdf_to_markdown.converters.{converter}")
    if converter == "docling":
        # RapidOCR deliberately disables propagation. Preserve its console
        # handler and attach our recorder to this pinned native warning channel.
        native_logger = importlib.import_module("rapidocr.utils.log").logger
        if not native_logger.propagate:
            for handler in logging.getLogger().handlers:
                if isinstance(handler, WarningLog):
                    native_logger.addHandler(handler)
    print(
        f"Preparing local {converter} models and converting {len(expected)} pages…",
        flush=True,
    )
    extracted = adapter.convert(source, stage, cache, expected)
    if extracted.pages != expected:
        raise ConversionError(
            f"Incomplete page processing: expected {expected}, got {extracted.pages}"
        )
    markdown = stage / extracted.markdown
    text = markdown.read_text(encoding="utf-8")
    references = [int(n) for n in re.findall(r"<!-- PDF page (\d+) -->", text)]
    if references != expected:
        raise ConversionError(
            f"Physical page references are incomplete or reordered: {references}"
        )
    linked = {image_file(stage, ref) for ref in image_references(text)}
    extracted.images = len(linked)
    data = extracted.to_dict()
    data["success"] = True
    return data


def runtime_details(converter: str) -> dict[str, Any]:
    data: dict[str, Any] = {
        "converter": converter,
        "converter_version": importlib.metadata.version(DISTRIBUTIONS[converter]),
        "runtime_versions": {},
    }
    for name in [
        "pymupdf",
        "Pillow",
        "torch",
        "transformers",
        "rapidocr",
        "onnxruntime",
        "surya-ocr",
        "docling-core",
        "docvortex",
    ]:
        try:
            data["runtime_versions"][name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            pass
    return data


def main() -> None:
    request_file, result_file = map(Path, sys.argv[1:3])
    handler = WarningLog()
    logging.getLogger().addHandler(handler)
    data: dict[str, Any] = {}
    exit_code = 0
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            request = json.loads(request_file.read_text(encoding="utf-8"))
            data = run(request)
        except Exception as exc:
            exit_code = 1
            data = {
                "success": False,
                "error": str(exc),
                "exception": type(exc).__name__,
                "traceback": traceback.format_exc(),
            }
        try:
            data.update(
                runtime_details(json.loads(request_file.read_text())["converter"])
            )
        except (OSError, KeyError, ValueError, importlib.metadata.PackageNotFoundError):
            pass
        pdf_module = sys.modules.get("pymupdf")
        if pdf_module is not None:
            handler.diagnostics.extend(
                Diagnostic(message, "mupdf")
                for message in pdf_module.TOOLS.mupdf_warnings().splitlines()
            )
        native = [warning.__dict__ for warning in handler.diagnostics]
        native.extend(
            Diagnostic(str(w.message), w.category.__name__).__dict__ for w in caught
        )
        data.setdefault("warnings", []).extend(native)
    # No PDF content is sent remotely. This digest identifies the input we used.
    try:
        source = Path(json.loads(request_file.read_text())["source"])
        with source.open("rb") as stream:
            data["input_sha256"] = hashlib.file_digest(stream, "sha256").hexdigest()
    except OSError:
        pass
    result_file.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()

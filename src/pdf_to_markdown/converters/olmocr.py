"""Local olmOCR pipeline with native Dolma page spans and strict coverage."""

import importlib
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from pdf_to_markdown.contracts import ConversionError, Diagnostic, Extraction
from pdf_to_markdown.converters.common import finish, page_comment, save_json

MODEL = "allenai/olmOCR-2-7B-1025-FP8"


def document_markdown(document: dict[str, Any], expected: list[int]) -> str:
    """Validate native processing evidence before inserting physical page markers."""
    metadata = document["metadata"]
    if metadata["total-fallback-pages"] != 0:
        raise ConversionError("olmOCR used fallback extraction for failed pages.")
    spans = document["attributes"]["pdf_page_numbers"]
    pages = [span[2] for span in spans]
    if pages != expected or metadata["pdf-total-pages"] != len(expected):
        raise ConversionError(f"olmOCR returned incomplete pages: {pages}")
    text = document["text"]
    if not isinstance(text, str):
        raise ConversionError("olmOCR returned invalid document text.")
    parts = []
    position = 0
    for start, stop, page in spans:
        if (
            type(start) is not int
            or type(stop) is not int
            or start != position
            or not start <= stop <= len(text)
        ):
            raise ConversionError("olmOCR returned invalid physical page spans.")
        parts.append(page_comment(page) + "\n\n" + text[start:stop])
        position = stop
    if position != len(text):
        raise ConversionError("olmOCR page spans do not cover the document text.")
    return "\n\n".join(parts)


def convert(source: Path, stage: Path, cache: Path, expected: list[int]) -> Extraction:
    if shutil.which("pdftoppm") is None or shutil.which("pdftotext") is None:
        raise ConversionError("olmOCR requires Poppler: install poppler-utils.")
    torch = importlib.import_module("torch")
    if not torch.cuda.is_available():
        raise ConversionError("olmOCR requires a compatible NVIDIA GPU with CUDA.")
    if torch.cuda.get_device_properties(0).total_memory < 15 * 1024**3:
        raise ConversionError("olmOCR requires at least 15 GiB of GPU memory.")
    options = {
        "model": MODEL,
        "local_inference": True,
        "ocr": "vision-language model on every page",
        "max_page_error_rate": 0,
        "workers": 1,
        "max_concurrent_requests": 1,
        "gpu_memory_utilization": 0.8,
        "max_model_len": 16384,
        "target_longest_image_dim": 1288,
    }
    # Keep queue files and transient model-server state out of published artifacts.
    with tempfile.TemporaryDirectory(prefix="pdf-to-markdown-olmocr-") as temporary:
        workspace = Path(temporary)
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        command = [
            sys.executable,
            "-m",
            "olmocr.pipeline",
            str(workspace),
            "--model",
            MODEL,
            "--max_page_error_rate",
            "0",
            "--workers",
            "1",
            "--max_concurrent_requests",
            "1",
            "--gpu-memory-utilization",
            "0.8",
            "--max_model_len",
            "16384",
            "--target_longest_image_dim",
            "1288",
            "--port",
            str(port),
            "--host",
            "127.0.0.1",
            "--pdfs",
            str(source),
        ]
        # No server/API options: olmOCR starts its own local vLLM process.
        environment = os.environ.copy()
        environment["PATH"] = str(Path(sys.executable).parent) + os.pathsep + os.defpath
        environment["VLLM_HOST_IP"] = "127.0.0.1"
        environment["VLLM_NO_USAGE_STATS"] = "1"
        process = subprocess.Popen(command, env=environment, start_new_session=True)

        def interrupted(signum: int, frame: Any) -> None:
            raise ConversionError("olmOCR conversion interrupted.")

        previous_handler = signal.signal(signal.SIGTERM, interrupted)
        try:
            code = process.wait()
        finally:
            signal.signal(signal.SIGTERM, previous_handler)
            # vLLM is a grandchild; terminate the whole private process group,
            # including on interruption or a native pipeline failure.
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        if code:
            raise ConversionError(f"olmOCR pipeline exited with code {code}.")
        documents = []
        for result in sorted((workspace / "results").glob("*.jsonl")):
            for line in result.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    documents.append(json.loads(line))
        if len(documents) != 1:
            raise ConversionError(
                f"olmOCR produced {len(documents)} documents; "
                "expected one complete PDF."
            )
        document = documents[0]
        if document["metadata"]["Source-File"] != str(source):
            raise ConversionError("olmOCR output does not match the input PDF.")
        text = document_markdown(document, expected)
    # Native figure filenames are model predictions, not extracted files. Their
    # coordinate system is unspecified; preserve the description instead of
    # guessing a crop. Embedded PDF figures are retained by finish below.
    placeholders = []

    def figure_description(match: re.Match[str]) -> str:
        placeholders.append(match.group(2))
        return match.group(1)

    text = re.sub(
        r"!\[([^\]\n]*)\]\((page_\d+_\d+_\d+_\d+\.png)\)",
        figure_description,
        text,
    )
    options["figure_placeholders"] = placeholders
    native = f"{source.stem}.dolma.json"
    save_json(stage / native, document)
    (stage / "images").mkdir()
    result = finish(
        stage,
        f"{source.stem}.md",
        text,
        expected,
        source=source,
        native_artifacts=[native],
        options=options,
    )
    if placeholders:
        result.warnings.append(
            Diagnostic(
                f"olmOCR emitted {len(placeholders)} figure placeholders without "
                "image files. Their descriptions were retained as text; embedded "
                "PDF images were extracted separately. Figures inside scans and "
                "vector-only figures may be absent. See native Dolma JSON.",
                "olmocr",
            )
        )
    return result

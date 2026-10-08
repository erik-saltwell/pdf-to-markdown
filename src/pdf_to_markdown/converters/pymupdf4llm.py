"""PyMuPDF4LLM layout extraction with explicitly local English OCR."""

import importlib
import io
import os
from pathlib import Path
from urllib.parse import quote

from pdf_to_markdown.assets import image_references
from pdf_to_markdown.contracts import ConversionError, Diagnostic, Extraction
from pdf_to_markdown.converters.common import (
    finish,
    occurrence,
    page_comment,
    save_json,
)
from pdf_to_markdown.models import english_tessdata


def convert(source: Path, stage: Path, cache: Path, expected: list[int]) -> Extraction:
    module = importlib.import_module("pymupdf4llm")
    module.use_layout(True)
    pdf_module = importlib.import_module("pymupdf")
    english_tessdata(pdf_module, cache)
    ocr = importlib.import_module("pymupdf4llm.ocr.tesseract_api")
    if ocr.TESSDATA is None or not (Path(ocr.TESSDATA) / "eng.traineddata").is_file():
        raise ConversionError(
            "Local Tesseract English data is not available; rerun setup."
        )
    native_messages = io.StringIO()
    pdf_module.set_messages(stream=native_messages)
    (stage / "images").mkdir()
    old_directory = Path.cwd()
    try:
        os.chdir(stage)
        with pdf_module.open(source) as pdf:
            chunks = module.to_markdown(
                pdf,
                filename=source.name,
                page_chunks=True,
                write_images=True,
                image_path="images",
                embed_images=False,
                header=True,
                footer=True,
                use_ocr=True,
                force_ocr=False,
                ocr_language="eng",
                ocr_function=ocr.exec_ocr,
                ocr_dpi=300,
                show_progress=True,
                table_output="html",
            )
        pages = [chunk["metadata"]["page_number"] for chunk in chunks]
        if pages != expected:
            raise ConversionError(f"PyMuPDF4LLM returned incomplete pages: {pages}")
        text = "\n\n".join(
            page_comment(page) + "\n\n" + chunk["text"]
            for page, chunk in zip(pages, chunks, strict=True)
        )
        # Native paths may contain spaces: encode only generated link destinations.
        for reference in image_references(text):
            text = text.replace(f"]({reference})", f"]({quote(reference, safe='/')})")
        occurrences = []
        with pdf_module.open(source) as pdf:
            for page, chunk in zip(pages, chunks, strict=True):
                for box in chunk["page_boxes"]:
                    if str(box["class"]).lower() == "picture":
                        start, stop = box["pos"]
                        for reference in image_references(chunk["text"][start:stop]):
                            occurrences.append(
                                occurrence(reference, page, box["bbox"], pdf)
                            )
        save_json(stage / f"{source.stem}.chunks.json", chunks)
        result = finish(
            stage,
            f"{source.stem}.md",
            text,
            pages,
            occurrences,
            native_artifacts=[f"{source.stem}.chunks.json"],
            options={
                "ocr": "tesseract",
                "language": "eng",
                "layout": True,
                "table_output": "html",
                "force_ocr": False,
            },
        )
        result.warnings.extend(
            Diagnostic(message, "pymupdf")
            for message in native_messages.getvalue().splitlines()
            if "warn" in message.lower() or "error" in message.lower()
        )
        return result
    finally:
        os.chdir(old_directory)

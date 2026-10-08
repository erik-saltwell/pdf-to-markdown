"""Marker's local Surya baseline, with native metadata and page pagination."""

import importlib
import re
import uuid
from pathlib import Path

from pdf_to_markdown.contracts import ConversionError, Extraction
from pdf_to_markdown.converters.common import (
    finish,
    occurrence,
    page_comment,
    save_json,
)


def convert(source: Path, stage: Path, cache: Path, expected: list[int]) -> Extraction:
    api = importlib.import_module("marker.converters.pdf")
    models = importlib.import_module("marker.models")
    renderers = importlib.import_module("marker.renderers.markdown")
    separator = f"PDF_TO_MARKDOWN_{uuid.uuid4().hex}"
    config = {
        "use_llm": False,
        "force_ocr": False,
        "paginate_output": True,
        "page_separator": separator,
        "html_tables_in_markdown": True,
        "disable_image_extraction": False,
        "keep_pageheader_in_output": True,
        "keep_pagefooter_in_output": True,
    }
    print("Preparing local Surya models (download progress follows)…", flush=True)
    converter = api.PdfConverter(
        artifact_dict=models.create_model_dict(), config=config
    )
    document = converter.build_document(str(source))
    rendered = renderers.MarkdownRenderer(config)(document)
    pages = [item["page_id"] + 1 for item in rendered.metadata["page_stats"]]
    if pages != expected:
        raise ConversionError(f"Marker returned incomplete page statistics: {pages}")
    text = re.sub(
        r"\{(\d+)\}" + re.escape(separator),
        lambda match: page_comment(int(match[1]) + 1),
        rendered.markdown,
    )
    (stage / "images").mkdir()
    for name, image in rendered.images.items():
        if Path(name).name != name:
            raise ConversionError(f"Unsafe Marker image name: {name}")
        image.save(stage / "images" / name)
        # Only native-generated destinations change; basenames stay native.
        text = text.replace(f"]({name})", f"](images/{name})")
        text = text.replace(f'src="{name}"', f'src="images/{name}"')
    native_report = f"{source.stem}_meta.json"
    save_json(stage / native_report, rendered.metadata)
    occurrences = []
    pdf_module = importlib.import_module("pymupdf")
    with pdf_module.open(source) as pdf:
        for page in document.pages:
            for block in page.children:
                for name in rendered.images:
                    if str(block.id).replace("/", "_").strip("_") in name:
                        occurrences.append(
                            occurrence(
                                f"images/{name}",
                                page.page_id + 1,
                                block.polygon.bbox,
                                pdf,
                                caption=None,
                            )
                        )
    return finish(
        stage,
        f"{source.stem}.md",
        text,
        pages,
        occurrences,
        source=source,
        native_report=native_report,
        options={
            "use_llm": False,
            "force_ocr": False,
            "ocr": "local-surya",
            "table_output": "html",
        },
    )

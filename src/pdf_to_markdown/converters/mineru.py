"""MinerU 4 Basic parsing, preserving original page indices and broken-page state."""

import importlib
import json
import logging
import os
from pathlib import Path
from typing import Any

from pdf_to_markdown.contracts import ConversionError, Extraction
from pdf_to_markdown.converters.common import finish, occurrence, page_comment


def convert(source: Path, stage: Path, cache: Path, expected: list[int]) -> Extraction:
    home = cache / "mineru"
    home.mkdir(parents=True, exist_ok=True)
    config_file = home / "app-config.json"
    config_file.write_text(
        json.dumps(
            {
                "model": {
                    "source": "auto",
                    "base_dir": str(home / "models"),
                    "small_backend": "onnx",
                    "vlm": {"server_url": ""},
                },
                "llm_aided": {
                    "features": {
                        "title_leveling": False,
                        "cross_page_table_cell_merge": False,
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    os.environ["MINERU_CONFIG"] = str(config_file)
    api = importlib.import_module("mineru.parser")
    loguru = importlib.import_module("loguru")
    sink = loguru.logger.add(
        lambda message: logging.getLogger(message.record["name"]).log(
            message.record["level"].no, message.record["message"]
        ),
        level="WARNING",
    )

    class StrictParser(api.MinerUParser):
        def _prepare_input(self, *args: Any, **kwargs: Any) -> Any:
            prepared = super()._prepare_input(*args, **kwargs)
            if prepared.broken_page_indices:
                pages = [number + 1 for number in prepared.broken_page_indices]
                raise ConversionError(
                    f"MinerU PDF rewrite failed on physical pages {pages}."
                )
            return prepared

    try:
        print(
            "Preparing MinerU Basic local ONNX models (download progress follows)…",
            flush=True,
        )
        parser = StrictParser(tier="basic", parse_mode="auto", image_analysis=True)
        result = parser.parse(source, page_range="all")
        pages = [page.page_idx + 1 for page in result.pages]
        if pages != expected or not result.middle_json.is_full_document:
            raise ConversionError(f"MinerU returned a partial document: {pages}")
        writer = importlib.import_module("mineru.parser.writer")
        result.save(writer.FileBasedDataWriter(str(stage)))
        exported = api.ParseResult.from_json((stage / "middle_json.json").read_text())
        renderer = importlib.import_module("mineru.render")
        parts = []
        occurrences = []
        pdf_module = importlib.import_module("pymupdf")
        with pdf_module.open(source) as pdf:
            for page in exported.pages:
                single_page = exported.middle_json.model_copy(update={"pages": [page]})
                parts.append(
                    page_comment(page.page_idx + 1)
                    + "\n\n"
                    + renderer.render_markdown(
                        single_page, mode=renderer.RenderMode.FULL
                    )
                )

                def blocks(items: Any) -> Any:
                    for item in items:
                        yield item
                        children = getattr(item, "content", None)
                        if isinstance(children, list):
                            yield from blocks(children)

                extra_images = []
                from urllib.parse import quote

                from pdf_to_markdown.assets import image_references

                linked = set(image_references(parts[-1]))
                for block in blocks(page.blocks):
                    image_path = getattr(block, "image_path", None)
                    bbox = getattr(block, "bbox", None)
                    if image_path and bbox:
                        rectangle = pdf[page.page_idx].rect
                        scaled = [
                            bbox[0] * rectangle.width,
                            bbox[1] * rectangle.height,
                            bbox[2] * rectangle.width,
                            bbox[3] * rectangle.height,
                        ]
                        occurrences.append(
                            occurrence(
                                image_path,
                                page.page_idx + 1,
                                scaled,
                                pdf,
                                caption=None,
                            )
                        )
                        if image_path not in linked:
                            extra_images.append(
                                f"![Source image]({quote(image_path, safe='/')})"
                            )
                            linked.add(image_path)
                if extra_images:
                    parts[-1] += "\n\n" + "\n\n".join(extra_images)
        extracted = finish(
            stage,
            "markdown.md",
            "\n\n".join(parts),
            pages,
            occurrences,
            native_artifacts=[
                "middle_json.json",
                "structured_content.json",
                "model_output.json",
            ],
            options={
                "tier": "basic",
                "small_backend": "onnx",
                "ocr_mode": "auto",
                "llm_aided": False,
            },
        )
        return extracted
    finally:
        loguru.logger.remove(sink)

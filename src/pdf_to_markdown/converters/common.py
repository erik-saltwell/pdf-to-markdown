"""Serialization helpers shared only where converter behavior coincides."""

import importlib
import json
from pathlib import Path
from typing import Any
from urllib.parse import quote

from pdf_to_markdown.contracts import Extraction
from pdf_to_markdown.images import filter_images


def retain_embedded_images(
    source: Path,
    stage: Path,
    text: str,
    folder: str,
    occurrences: list[dict[str, Any]],
) -> tuple[str, list[str]]:
    """Keep source bitmaps omitted by native figure classification.

    This preserves embedded assets, never rasterizes a page or substitutes for
    its extracted text. Full-page scan inputs remain the OCR engine's input.
    """
    from pdf_to_markdown.assets import image_references

    pdf_module = importlib.import_module("pymupdf")
    linked = set(image_references(text))
    retained = []
    with pdf_module.open(source) as pdf:
        for page in pdf:
            additions = []
            for index, image in enumerate(page.get_image_info(xrefs=True)):
                rect = pdf_module.Rect(image["bbox"])
                if not image["xref"] or rect.is_empty:
                    continue
                # A page-sized bitmap is scan input, not a newly found figure.
                if (
                    not page.get_text("words")
                    and (rect & page.rect).get_area() >= page.rect.get_area() * 0.995
                ):
                    continue
                covered = any(
                    item["page"] == page.number + 1
                    and quote(item["path"], safe="/") in linked
                    and (rect & pdf_module.Rect(item["bbox"])).get_area()
                    >= rect.get_area() * 0.9
                    for item in occurrences
                )
                if covered:
                    continue
                name = (
                    f"{folder}/source-page-{page.number + 1:04d}"
                    f"-image-{index + 1:04d}.png"
                )
                destination = stage / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                original = pdf.extract_image(image["xref"])
                bitmap = pdf_module.Pixmap(original["image"])
                if original.get("smask"):
                    mask = pdf_module.Pixmap(pdf, original["smask"])
                    bitmap = pdf_module.Pixmap(bitmap, mask)
                if bitmap.colorspace and bitmap.colorspace.n > 3:
                    bitmap = pdf_module.Pixmap(pdf_module.csRGB, bitmap)
                bitmap.save(destination)
                additions.append(f"![Source image]({quote(name, safe='/')})")
                retained.append(name)
                occurrences.append(occurrence(name, page.number + 1, tuple(rect), pdf))
            if additions:
                following = page_comment(page.number + 2)
                extra = "\n\n" + "\n\n".join(additions) + "\n\n"
                if following in text:
                    text = text.replace(following, extra + following, 1)
                else:
                    text += extra
    return text, retained


def page_comment(page: int) -> str:
    return f"<!-- PDF page {page} -->"


def occurrence(
    path: str,
    page: int,
    bbox: list[float] | tuple[float, ...],
    pdf: Any,
    caption: bool | None = None,
) -> dict[str, Any]:
    source = pdf[page - 1]
    rect = importlib.import_module("pymupdf").Rect(bbox)
    words = source.get_text("words")
    width, height = source.rect.width, source.rect.height
    peripheral = (
        rect.x1 <= width * 0.12
        or rect.x0 >= width * 0.88
        or rect.y1 <= height * 0.12
        or rect.y0 >= height * 0.88
        or (
            rect.x0 < width * 0.03
            and rect.y0 < height * 0.03
            and rect.x1 > width * 0.97
            and rect.y1 > height * 0.97
        )
    )
    outside = not any(
        rect.intersects(importlib.import_module("pymupdf").Rect(w[:4])) for w in words
    )
    for image in source.get_images():
        for other in source.get_image_rects(image[0]):
            if tuple(other) != tuple(rect) and rect.intersects(other):
                outside = False
    return {
        "path": path,
        "page": page,
        "bbox": list(bbox),
        "normalized_bbox": [
            rect.x0 / width,
            rect.y0 / height,
            rect.x1 / width,
            rect.y1 / height,
        ],
        "caption": caption,
        "usable_embedded_text": bool(words),
        "peripheral": peripheral,
        "outside_content": outside,
    }


def finish(
    stage: Path,
    name: str,
    text: str,
    pages: list[int],
    occurrences: list[dict[str, Any]] | None = None,
    source: Path | None = None,
    image_folder: str = "images",
    **kwargs: Any,
) -> Extraction:
    occurrences = occurrences or []
    if source is not None:
        text, retained = retain_embedded_images(
            source, stage, text, image_folder, occurrences
        )
        kwargs.setdefault("options", {})["retained_source_images"] = retained
    text, filtered, warnings = filter_images(text, stage, occurrences or [])
    (stage / name).write_text(text, encoding="utf-8")
    return Extraction(
        name, pages, warnings=warnings, filtered_images=filtered, **kwargs
    )


def save_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )

"""Evidence-based decoration filtering; uncertain visuals always survive."""

import importlib
from collections import defaultdict
from pathlib import Path
from typing import Any

from pdf_to_markdown.assets import image_file, image_references, remove_image_reference
from pdf_to_markdown.contracts import Diagnostic
from pdf_to_markdown.output import digest


def blank_or_border(path: Path) -> tuple[bool, bool]:
    image_module = importlib.import_module("PIL.Image")
    with image_module.open(path) as image:
        rgba = image.convert("RGBA")
        if rgba.getchannel("A").getbbox() is None:
            return True, False
        if rgba.getchannel("A").getextrema() != (255, 255):
            # White symbols on transparency can be visible on a dark map.
            # Compositing onto white would falsely classify them as blank.
            return False, False
        background = image_module.new("RGBA", rgba.size, "white")
        background.alpha_composite(rgba)
        rgb = background.convert("RGB")
        white = all(low == high == 255 for low, high in rgb.getextrema())
        width, height = rgb.size
        if width < 50 or height < 50:
            return white, False
        inset_x, inset_y = max(1, width // 25), max(1, height // 25)
        center = rgb.crop((inset_x, inset_y, width - inset_x, height - inset_y))
        border = not white and all(
            low == high == 255 for low, high in center.getextrema()
        )
        if border:
            # A solid outline has uniform runs along all four sides. Marks,
            # corner symbols, text or ornamentation make the purpose uncertain.
            sides = [
                rgb.crop((inset_x, 0, width - inset_x, inset_y)),
                rgb.crop((inset_x, height - inset_y, width - inset_x, height)),
                rgb.crop((0, inset_y, inset_x, height - inset_y)).transpose(
                    image_module.Transpose.TRANSPOSE
                ),
                rgb.crop((width - inset_x, inset_y, width, height - inset_y)).transpose(
                    image_module.Transpose.TRANSPOSE
                ),
            ]
            for side in sides:
                if all(low == high == 255 for low, high in side.getextrema()):
                    border = False
                for row in range(side.height):
                    extrema = side.crop((0, row, side.width, row + 1)).getextrema()
                    if any(low != high for low, high in extrema):
                        border = False
        return white, border


def filter_images(
    markdown: str,
    root: Path,
    occurrences: list[dict[str, Any]],
) -> tuple[str, list[dict[str, Any]], list[Diagnostic]]:
    """Filter blank images or repeated border-only crops with source evidence."""
    by_source = defaultdict(list)
    for occurrence in occurrences:
        by_source[occurrence["path"]].append(occurrence)
    refs = image_references(markdown)
    decisions = []
    warnings = []
    properties = {}
    hashes = defaultdict(list)
    for source in set(refs):
        path = image_file(root, source)
        try:
            properties[source] = blank_or_border(path)
            hashes[digest(path)].append(source)
        except (OSError, ValueError) as exc:
            warnings.append(
                Diagnostic(f"Kept image; filtering unavailable: {exc}", "image-filter")
            )
    for source, (blank, border) in properties.items():
        reason = "demonstrably blank or transparent" if blank else None
        if border and reason is None:
            matching = hashes[digest(image_file(root, source))]
            evidence = [
                item for name in matching for item in by_source[unquote_path(name)]
            ]
            positions = [item.get("normalized_bbox") for item in evidence]
            stable = all(positions) and all(
                max(position[axis] for position in positions)
                - min(position[axis] for position in positions)
                <= 0.01
                for axis in range(4)
            )
            if (
                stable
                and len({item["page"] for item in evidence}) >= 3
                and all(
                    item.get("outside_content")
                    and item.get("peripheral")
                    and item.get("usable_embedded_text")
                    and item.get("caption") is False
                    for item in evidence
                )
            ):
                reason = (
                    "matching border-only pixels on >=3 pages, "
                    "outside content, no caption"
                )
        if reason is None:
            continue
        changed = remove_image_reference(markdown, source)
        if source in image_references(changed):
            continue  # No reliable way to remove this syntax: retain the asset.
        markdown = changed
        decisions.append({"asset": source, "reason": reason})
    retained = {image_file(root, source) for source in image_references(markdown)}
    candidates = {image_file(root, decision["asset"]) for decision in decisions}
    for path in candidates:
        native_reference = any(
            path.name in artifact.read_text(encoding="utf-8")
            for artifact in root.rglob("*.json")
        )
        if path not in retained and not native_reference:
            path.unlink()
    return markdown, decisions, warnings


def unquote_path(value: str) -> str:
    from urllib.parse import unquote

    return unquote(value)

"""Parse generated local image references without re-rendering Markdown."""

import importlib
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

from pdf_to_markdown.contracts import ConversionError


class ImageTags(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.sources: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "img":
            source = dict(attrs).get("src")
            if source:
                self.sources.append(source)


def image_references(markdown: str) -> list[str]:
    parser = importlib.import_module("markdown_it").MarkdownIt("commonmark")
    sources: list[str] = []
    for token in parser.parse(markdown):
        for child in token.children or []:
            if child.type == "image":
                source = child.attrGet("src")
                if isinstance(source, str):
                    sources.append(source)
            if child.type == "html_inline":
                tags = ImageTags()
                tags.feed(child.content)
                sources.extend(tags.sources)
        if token.type == "html_block":
            tags = ImageTags()
            tags.feed(token.content)
            sources.extend(tags.sources)
    return sources


def image_file(root: Path, source: str) -> Path:
    parsed = urlsplit(source)
    if parsed.scheme or parsed.netloc or parsed.query:
        raise ConversionError(f"Image must be a local relative asset: {source}")
    relative = Path(unquote(parsed.path))
    if relative.is_absolute() or ".." in relative.parts:
        raise ConversionError(f"Image reference escapes output: {source}")
    path = root / relative
    if not path.resolve().is_relative_to(root.resolve()) or path.is_symlink():
        raise ConversionError(f"Unsafe image reference: {source}")
    if not path.is_file():
        raise ConversionError(f"Linked image is missing: {source}")
    return path


def remove_image_reference(markdown: str, source: str) -> str:
    """Remove only simple generated nodes; ambiguous syntax is retained."""
    pattern = (
        r"!\[[^\]\n]*\]\(\s*<?" + re.escape(source) + r">?(?:[ \t]+\"[^\"]*\")?\s*\)"
    )
    result = re.sub(pattern, "", markdown)
    for match in list(re.finditer(r"<img\b[^>]*>", result, re.IGNORECASE))[::-1]:
        tags = ImageTags()
        tags.feed(match.group())
        if tags.sources == [source]:
            result = result[: match.start()] + result[match.end() :]
    return result

"""Docling standard PDF pipeline and provenance-aware native serialization."""

import importlib
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from pdf_to_markdown.contracts import ConversionError, Diagnostic, Extraction
from pdf_to_markdown.converters.common import finish, occurrence, page_comment


def convert(source: Path, stage: Path, cache: Path, expected: list[int]) -> Extraction:
    options = importlib.import_module("docling.datamodel.pipeline_options")
    downloader = importlib.import_module("docling.utils.model_downloader")
    print(
        "Preparing layout, tables and English OCR weights (download progress follows)…",
        flush=True,
    )
    artifacts = downloader.download_models(
        output_dir=cache / "docling",
        progress=True,
        with_code_formula=False,
        with_picture_classifier=False,
        rapidocr_models=["onnxruntime:en"],
    )
    pipeline = options.PdfPipelineOptions(
        artifacts_path=artifacts,
        do_ocr=True,
        do_table_structure=True,
        ocr_options=options.RapidOcrOptions(
            lang=["en"],
            backend="onnxruntime",
            rapidocr_params={
                "EngineConfig.onnxruntime.use_cuda": False,
                "Det.use_cuda": False,
                "Cls.use_cuda": False,
                "Rec.use_cuda": False,
            },
        ),
        enable_remote_services=False,
        do_picture_description=False,
        do_picture_classification=False,
        do_code_enrichment=False,
        do_formula_enrichment=False,
        generate_picture_images=True,
        generate_page_images=False,
        images_scale=2.0,
    )
    api = importlib.import_module("docling.document_converter")
    base = importlib.import_module("docling.datamodel.base_models")
    converter = api.DocumentConverter(
        format_options={
            base.InputFormat.PDF: api.PdfFormatOption(pipeline_options=pipeline),
        }
    )
    converted = converter.convert(source, raises_on_error=False)
    if converted.status != base.ConversionStatus.SUCCESS:
        failures = "; ".join(str(error.error_message) for error in converted.errors)
        raise ConversionError(f"Docling {converted.status.value}: {failures}")
    pages = [page.page_no for page in converted.pages]
    if pages != expected:
        raise ConversionError(f"Docling did not complete every page: {pages}")
    types = importlib.import_module("docling_core.types.doc")
    document = converted.document
    document.save_as_json(stage / f"{source.stem}.docling.json")
    images_folder = f"{source.stem}_artifacts"
    referenced = document._with_pictures_refs(
        image_dir=stage / images_folder,
        page_no=None,
        reference_path=stage,
        include_page_images=False,
        uri_prefix=images_folder + "/",
    )
    serializers = importlib.import_module("docling_core.transforms.serializer.markdown")
    serializer_common = importlib.import_module(
        "docling_core.transforms.serializer.common"
    )
    html = importlib.import_module("docling_core.transforms.serializer.html")

    class NumberedSerializer(serializers.MarkdownDocSerializer):
        def serialize_doc(self, *, parts: list[Any], **kwargs: Any) -> Any:
            text = "\n\n".join(part.text for part in parts if part.text)
            for match, previous, following in self._get_page_breaks(text):
                text = text.replace(
                    match,
                    "\n\n".join(
                        page_comment(page)
                        for page in range(previous + 1, following + 1)
                    ),
                )
            return serializer_common.create_ser_result(text=text, span_source=parts)

    # HTML table serialization preserves spans; native serializers retain prose.
    serializer = NumberedSerializer(
        doc=referenced,
        table_serializer=html.HTMLTableSerializer(),
        params=serializers.MarkdownParams(
            image_mode=types.ImageRefMode.REFERENCED,
            layers={types.ContentLayer.BODY, types.ContentLayer.FURNITURE},
            page_break_placeholder="numbered",
            traverse_pictures=True,
        ),
    )
    text = serializer.serialize().text
    item_pages = [
        item.prov[0].page_no
        for item, _ in referenced.iterate_items()
        if getattr(item, "prov", None)
    ]
    first = min(item_pages, default=len(expected))
    text = (
        "\n\n".join(page_comment(page) for page in range(1, first + 1)) + "\n\n" + text
    )
    for page in expected:
        if page_comment(page) not in text:
            # A native blank trailing page has no items to trigger a boundary.
            if page in item_pages:
                raise ConversionError(
                    f"Docling serialization lost page boundary {page}."
                )
            text += "\n\n" + page_comment(page)
    pdf_module = importlib.import_module("pymupdf")
    occurrences = []
    with pdf_module.open(source) as pdf:
        for picture in referenced.pictures:
            if not picture.prov or picture.image is None:
                continue
            prov = picture.prov[0]
            bbox = prov.bbox.to_top_left_origin(
                page_height=pdf[prov.page_no - 1].rect.height
            )
            occurrences.append(
                occurrence(
                    unquote(str(picture.image.uri)),
                    prov.page_no,
                    bbox.as_tuple(),
                    pdf,
                    caption=bool(picture.captions),
                )
            )
    result = finish(
        stage,
        f"{source.stem}.md",
        text,
        pages,
        occurrences,
        source=source,
        image_folder=images_folder,
        native_artifacts=[f"{source.stem}.docling.json"],
        options={
            "ocr": "rapidocr-onnx",
            "language": "en",
            "remote_services": False,
            "table_output": "html",
            "images_scale": 2.0,
        },
    )
    result.warnings.extend(
        Diagnostic(
            error.error_message, error.module_name, getattr(error, "page_no", None)
        )
        for error in converted.errors
    )
    return result

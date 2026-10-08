"""Small missing model downloads outside the converters' native downloaders."""

import hashlib
import os
import tempfile
import urllib.request
from pathlib import Path

from pdf_to_markdown.contracts import ConversionError

ENGLISH_URL = (
    "https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/4.1.0/"
    "eng.traineddata"
)
ENGLISH_SHA256 = "7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2"


def english_tessdata(pdf_module: object, cache: Path) -> Path:
    from typing import Any, cast

    native = cast(Any, pdf_module).get_tessdata()
    if native and (Path(native) / "eng.traineddata").is_file():
        return Path(native)
    folder = cache / "tessdata"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / "eng.traineddata"
    if (
        not target.exists()
        or hashlib.sha256(target.read_bytes()).hexdigest() != ENGLISH_SHA256
    ):
        descriptor, temporary = tempfile.mkstemp(prefix=".english-", dir=folder)
        temporary_path = Path(temporary)
        try:
            print("Downloading local English Tesseract model…", flush=True)
            with os.fdopen(descriptor, "wb") as stream:
                with urllib.request.urlopen(ENGLISH_URL, timeout=60) as response:
                    total = response.headers.get("Content-Length", "unknown")
                    received = 0
                    hasher = hashlib.sha256()
                    while chunk := response.read(1024 * 1024):
                        received += len(chunk)
                        hasher.update(chunk)
                        stream.write(chunk)
                        print(
                            f"English OCR model: {received}/{total} bytes", flush=True
                        )
                stream.flush()
                os.fsync(stream.fileno())
            if hasher.hexdigest() != ENGLISH_SHA256:
                raise ConversionError("English OCR model checksum does not match.")
            temporary_path.replace(target)
        finally:
            temporary_path.unlink(missing_ok=True)
    os.environ["TESSDATA_PREFIX"] = str(folder)
    return folder

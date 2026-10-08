"""Native report supplements and separate diagnostics for unsuccessful runs."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def timestamp() -> str:
    return datetime.now(UTC).isoformat()


def save_report(stage: Path, worker: dict[str, Any], report: dict[str, Any]) -> str:
    native = worker.get("native_report")
    if native:
        path = stage / native
        data = json.loads(path.read_text(encoding="utf-8"))
        data["pdf_to_markdown"] = report
    else:
        path = stage / "conversion-report.json"
        data = report
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return path.name


def save_failure(output: Path, run_id: str, report: dict[str, Any]) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    path = output.parent / f".{output.name}.failed-{run_id}.report.json"
    with path.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    return path


def save_publication_warning(output: Path, run_id: str, report: dict[str, Any]) -> Path:
    """Late cleanup diagnostics cannot mutate the committed owned report."""
    path = output.parent / f".{output.name}.publication-{run_id}.report.json"
    with path.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    return path

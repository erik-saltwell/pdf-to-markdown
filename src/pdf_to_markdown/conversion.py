"""One-book orchestration: workers extract; only a validated result is published."""

import json
import subprocess
import tempfile
import uuid
from importlib.metadata import version
from pathlib import Path
from typing import Any

from pdf_to_markdown.contracts import ArgumentError, ConversionError
from pdf_to_markdown.output import OutputTransaction, digest
from pdf_to_markdown.reports import (
    save_failure,
    save_publication_warning,
    save_report,
    timestamp,
)
from pdf_to_markdown.runtimes import runtime_python
from pdf_to_markdown.settings import Converter


def invoke_worker(python: Path, request: dict[str, Any]) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="pdf-to-markdown-worker-") as temporary:
        root = Path(temporary)
        request_file = root / "request.json"
        result_file = root / "result.json"
        request_file.write_text(json.dumps(request), encoding="utf-8")
        bundle = Path(__file__).resolve().parents[1]
        bootstrap = (
            "import sys,runpy;sys.path.insert(0,sys.argv.pop(1));"
            "runpy.run_module('pdf_to_markdown.worker',run_name='__main__')"
        )
        process = subprocess.Popen(
            [
                str(python),
                "-I",
                "-c",
                bootstrap,
                str(bundle),
                str(request_file),
                str(result_file),
            ]
        )
        try:
            code = process.wait()
        except BaseException:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            raise
        if not result_file.exists():
            raise ConversionError(f"Converter process exited {code} without a result.")
        result = json.loads(result_file.read_text(encoding="utf-8"))
        if code != 0 or result.get("success") is not True:
            result["success"] = False
        return result


def convert_pdf(source: Path, output: Path, converter: Converter) -> dict[str, Any]:
    if not source.is_file():
        raise ArgumentError(f"Input PDF is not a file: {source}")
    source = source.resolve()
    output = output.absolute()
    run_id = uuid.uuid4().hex
    report: dict[str, Any] = {
        "run_id": run_id,
        "started_at": timestamp(),
        "converter": converter.value,
        "application_version": version("pdf-to-markdown"),
        "input": str(source),
        "output": str(output),
        "status": "failed",
        "accuracy_verified": False,
        "diagnostic_limitations": "Native converter and application processing "
        "diagnostics only; no content-accuracy heuristics. "
        "No warnings does not establish correct or complete extracted content.",
        "warnings": [],
    }
    try:
        with OutputTransaction(output, source) as transaction:
            assert transaction.stage is not None
            python = runtime_python(converter)
            report["input_sha256"] = digest(source)
            request = {
                "source": str(source),
                "stage": str(transaction.stage),
                "converter": converter.value,
                "run_id": run_id,
            }
            inspected = invoke_worker(python, request | {"operation": "inspect"})
            if not inspected["success"]:
                report.update(inspected)
                raise ConversionError(inspected["error"])
            for key in ("converter_version", "runtime_versions"):
                report[key] = inspected[key]
            report["warnings"] = inspected.get("warnings", [])
            report["pages_in_input"] = len(inspected["pages"])
            extracted = invoke_worker(python, request)
            report["warnings"].extend(extracted.get("warnings", []))
            for key in (
                "converter_version",
                "runtime_versions",
                "options",
                "exception",
                "traceback",
            ):
                if key in extracted:
                    report[key] = extracted[key]
            if not extracted["success"]:
                raise ConversionError(extracted["error"])
            if extracted["input_sha256"] != report["input_sha256"]:
                raise ConversionError("Input PDF changed during conversion.")
            report.update(
                {
                    "status": "completed",
                    "finished_at": timestamp(),
                    "pages_processed": len(extracted["pages"]),
                    "images_saved": extracted["images"],
                    "filtered_images": extracted["filtered_images"],
                    "markdown": extracted["markdown"],
                    "native_artifacts": extracted["native_artifacts"],
                }
            )
            report_name = save_report(transaction.stage, extracted, report)
            cleanup_warnings = transaction.publish(converter.value, run_id)
            report["report_path"] = str(output / report_name)
            report["warnings"].extend(
                {"message": message, "source": "publication"}
                for message in cleanup_warnings
            )
            if cleanup_warnings:
                try:
                    supplemental = save_publication_warning(output, run_id, report)
                    report["report_path"] = str(supplemental)
                except OSError as exc:
                    report["warnings"].append(
                        {
                            "message": f"Could not save cleanup diagnostics: {exc}",
                            "source": "publication",
                        }
                    )
            return report
    except ArgumentError:
        raise
    except (Exception, KeyboardInterrupt) as exc:
        report.update(
            {
                "status": "failed",
                "error": str(exc) or "Interrupted",
                "finished_at": timestamp(),
            }
        )
        try:
            report_path = save_failure(output, run_id, report)
            message = f"{report['error']}\nFailure report: {report_path}"
        except OSError as report_error:
            message = (
                f"{report['error']}\nCould not save failure report: {report_error}"
            )
        raise ConversionError(message) from exc

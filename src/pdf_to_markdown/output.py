"""Owned-file replacement using a journal and atomic Linux directory exchange."""

import ctypes
import errno
import fcntl
import hashlib
import json
import os
import shutil
import stat
import tempfile
import uuid
from pathlib import Path, PurePosixPath
from typing import Any

from pdf_to_markdown.contracts import ArgumentError, ConversionError

MANIFEST = ".pdf-to-markdown-manifest.json"
APPLICATION = "pdf-to-markdown"


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def safe_relative(value: str) -> Path:
    path = PurePosixPath(value)
    if (
        not value
        or path.is_absolute()
        or any(p in {".", ".."} for p in value.split("/"))
    ):
        raise ConversionError(f"Unsafe generated path: {value!r}")
    return Path(path)


def flush_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def write_json(path: Path, data: dict[str, Any]) -> None:
    """Durably replace an internal record in its existing parent directory."""
    temporary = path.with_name(f".{path.name}-{uuid.uuid4().hex}")
    try:
        with temporary.open("x", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
        flush_directory(path.parent)
    finally:
        temporary.unlink(missing_ok=True)


def inventory(root: Path) -> dict[str, dict[str, Any]]:
    result = {}
    for path in sorted(root.rglob("*")):
        metadata = path.lstat()
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            result[relative] = {"symlink": os.readlink(path)}
        elif stat.S_ISREG(metadata.st_mode):
            result[relative] = {
                "sha256": digest(path),
                "size": metadata.st_size,
                "mode": stat.S_IMODE(metadata.st_mode),
            }
        elif stat.S_ISDIR(metadata.st_mode):
            result[relative] = {
                "directory": True,
                "mode": stat.S_IMODE(metadata.st_mode),
            }
        else:
            raise ConversionError(f"Unsupported special file in output: {path}")
    return result


def read_manifest(root: Path) -> dict[str, Any] | None:
    path = root / MANIFEST
    if not path.exists() and not path.is_symlink():
        return None
    try:
        if path.is_symlink():
            raise ValueError("manifest is a symlink")
        data = json.loads(path.read_text(encoding="utf-8"))
        if data["application"] != APPLICATION or data["schema_version"] != 1:
            raise ValueError("unsupported manifest")
        if not isinstance(data["generation"], str) or not isinstance(
            data["files"], dict
        ):
            raise ValueError("invalid manifest fields")
        for value, record in data["files"].items():
            relative = safe_relative(value)
            file = root / relative
            for parent in [file, *file.parents]:
                if parent == root:
                    break
                if parent.is_symlink():
                    raise ValueError(f"owned path is a symlink: {value}")
            if not file.is_file() or digest(file) != record["sha256"]:
                raise ValueError(f"generated file was removed or edited: {value}")
        for value in data.get("directories", []):
            safe_relative(value)
        return data
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ConversionError(f"Cannot safely replace {root}: {exc}") from exc


def exchange(left: Path, right: Path) -> None:
    library = ctypes.CDLL(None, use_errno=True)
    try:
        rename = library.renameat2
    except AttributeError as exc:
        raise ConversionError("Atomic directory exchange is unavailable.") from exc
    rename.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    rename.restype = ctypes.c_int
    if rename(-100, os.fsencode(left), -100, os.fsencode(right), 2) != 0:
        code = ctypes.get_errno()
        raise OSError(code, os.strerror(code), str(right))


def generation(root: Path) -> str | None:
    try:
        return json.loads((root / MANIFEST).read_text())["generation"]
    except (OSError, ValueError, KeyError, TypeError):
        return None


class OutputTransaction:
    """Serialize publishers and retain the previous generation until commit."""

    def __init__(self, output: Path, source: Path) -> None:
        if output.is_symlink():
            raise ArgumentError("The output folder must not be a symlink.")
        self.output = output.resolve()
        if (
            self.output == Path(self.output.anchor)
            or self.output == Path.cwd().resolve()
            or self.output == Path(__file__).resolve().parents[2]
        ):
            raise ArgumentError(
                "Choose a result folder, not the filesystem/current root."
            )
        if self.output.exists() and not self.output.is_dir():
            raise ArgumentError("The output must be a folder.")
        if source.resolve().is_relative_to(self.output):
            raise ArgumentError("The input PDF must be outside the output folder.")
        self.output.parent.mkdir(parents=True, exist_ok=True)
        key = hashlib.sha256(os.fsencode(self.output)).hexdigest()[:20]
        self.journal = self.output.parent / f".pdf-to-markdown-{key}.transaction.json"
        self.lock_path = self.output.parent / f".pdf-to-markdown-{key}.lock"
        self.lock: Any = None
        self.stage: Path | None = None
        self.old_manifest: dict[str, Any] | None = None
        self.old_inventory: dict[str, dict[str, Any]] = {}

    def __enter__(self) -> "OutputTransaction":
        self.lock = self.lock_path.open("a+")
        try:
            fcntl.flock(self.lock.fileno(), fcntl.LOCK_EX)
            self.recover()
            if self.output.exists():
                self.old_manifest = read_manifest(self.output)
                self.old_inventory = inventory(self.output)
            self.stage = Path(
                tempfile.mkdtemp(
                    prefix=f".{self.output.name}.extract-", dir=self.output.parent
                )
            )
            return self
        except BaseException:
            self.lock.close()
            raise

    def __exit__(self, *_: object) -> None:
        if self.stage is not None:
            shutil.rmtree(self.stage, ignore_errors=True)
        if self.lock is not None:
            self.lock.close()

    def recover(self, *, rollback: bool = False) -> None:
        if not self.journal.exists():
            return
        data = json.loads(self.journal.read_text())
        candidate = Path(data["candidate"])
        if (
            candidate.parent != self.output.parent
            or not candidate.name.startswith(f".{self.output.name}.candidate-")
            or candidate.is_symlink()
            or data["output"] != str(self.output)
            or data["state"] not in {"prepared", "committed"}
            or not isinstance(data["had_output"], bool)
            or not isinstance(data["candidate_inventory"], dict)
        ):
            raise ConversionError(f"Invalid recovery journal: {self.journal}")
        swapped = generation(self.output) == data["new_generation"]
        if (rollback or data["state"] != "committed") and swapped:
            if inventory(self.output) != data["candidate_inventory"]:
                raise ConversionError(
                    "Published folder changed after interruption; preserve both "
                    f"{self.output} and {candidate} for manual recovery."
                )
            if data["had_output"]:
                if not candidate.is_dir():
                    raise ConversionError(f"Rollback backup is missing: {candidate}")
                exchange(candidate, self.output)
            else:
                self.output.rename(candidate)
            flush_directory(self.output.parent)
        elif data["state"] == "committed" and not swapped:
            raise ConversionError(
                "Committed output identity changed; preserve the backup."
            )
        elif data["state"] != "committed" and not swapped:
            if (
                not candidate.is_dir()
                or inventory(candidate) != data["candidate_inventory"]
            ):
                raise ConversionError(
                    "Interrupted output identity changed; preserve the backup."
                )
        if candidate.exists():
            shutil.rmtree(candidate)
        self.journal.unlink()
        flush_directory(self.output.parent)

    def publish(self, converter: str, run_id: str) -> list[str]:
        assert self.stage is not None
        files = inventory(self.stage)
        if any("symlink" in record for record in files.values()):
            raise ConversionError("Generated output contains a symlink.")
        old_owned = set((self.old_manifest or {}).get("files", {}))
        for value, record in files.items():
            existing = self.old_inventory.get(value)
            if (
                "directory" not in record
                and existing is not None
                and value not in old_owned
            ):
                raise ConversionError(
                    f"Generated output collides with unrelated file: {value}"
                )
            if "directory" in record and existing and "directory" not in existing:
                raise ConversionError(
                    f"An unrelated file blocks generated folder: {value}"
                )
        candidate = Path(
            tempfile.mkdtemp(
                prefix=f".{self.output.name}.candidate-", dir=self.output.parent
            )
        )
        journal_written = False
        committed = False
        warnings = []
        try:
            if self.output.exists():
                shutil.copytree(
                    self.output, candidate, dirs_exist_ok=True, symlinks=True
                )
                for value in old_owned:
                    (candidate / safe_relative(value)).unlink()
                (candidate / MANIFEST).unlink(missing_ok=True)
                for value in sorted(
                    (self.old_manifest or {}).get("directories", []),
                    key=lambda v: v.count("/"),
                    reverse=True,
                ):
                    try:
                        (candidate / safe_relative(value)).rmdir()
                    except OSError as exc:
                        if exc.errno not in {errno.ENOTEMPTY, errno.ENOENT}:
                            raise
            shutil.copytree(self.stage, candidate, dirs_exist_ok=True)
            owned_files = {
                value: record
                for value, record in files.items()
                if "directory" not in record
            }
            old_directories = set((self.old_manifest or {}).get("directories", []))
            owned_directories = [
                value
                for value, record in files.items()
                if "directory" in record
                and (value not in self.old_inventory or value in old_directories)
            ]
            write_json(
                candidate / MANIFEST,
                {
                    "application": APPLICATION,
                    "schema_version": 1,
                    "generation": run_id,
                    "converter": converter,
                    "files": owned_files,
                    "directories": owned_directories,
                },
            )
            for path in candidate.rglob("*"):
                if path.is_file() and not path.is_symlink():
                    with path.open("rb") as stream:
                        os.fsync(stream.fileno())
            for path in sorted(
                (p for p in candidate.rglob("*") if p.is_dir() and not p.is_symlink()),
                reverse=True,
            ):
                flush_directory(path)
            flush_directory(candidate)
            current = inventory(self.output) if self.output.exists() else {}
            if current != self.old_inventory:
                raise ConversionError(
                    "Output changed during conversion; replacement aborted."
                )
            transaction = {
                "output": str(self.output),
                "candidate": str(candidate),
                "new_generation": run_id,
                "had_output": self.output.exists(),
                "state": "prepared",
                "candidate_inventory": inventory(candidate),
            }
            write_json(self.journal, transaction)
            journal_written = True
            if transaction["had_output"]:
                exchange(candidate, self.output)
            else:
                candidate.rename(self.output)
            flush_directory(self.output.parent)
            transaction["state"] = "committed"
            write_json(self.journal, transaction)
            committed = True
        except BaseException:
            if journal_written:
                try:
                    self.recover(rollback=True)
                except Exception as exc:
                    raise ConversionError(
                        f"Publication recovery failed: {exc}. Preserve {candidate} "
                        f"and {self.journal}; they contain recovery information."
                    ) from exc
            raise
        finally:
            if not journal_written and candidate.exists():
                shutil.rmtree(candidate)
        if committed:
            try:
                self.recover()
            except OSError as exc:
                warnings.append(f"Output committed; backup cleanup deferred: {exc}")
        return warnings

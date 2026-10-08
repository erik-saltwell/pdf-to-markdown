"""Load and validate application settings."""

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import yaml


class Converter(StrEnum):
    """Available converter selections."""

    DOCLING = "docling"
    MARKER = "marker"
    PYMUPDF4LLM = "pymupdf4llm"
    MINERU = "mineru"


@dataclass(frozen=True)
class Settings:
    """Validated application configuration."""

    converter: Converter = Converter.DOCLING


class SettingsError(ValueError):
    """An unreadable or invalid settings file."""


def load_settings(path: Path | None = None) -> Settings:
    """Read settings.yaml in the working directory, or an explicit file.

    Use defaults when the implicit settings file is absent. An explicit path
    must exist so a typo cannot silently change the selected converter.
    """
    settings_path = path if path is not None else Path("settings.yaml")
    try:
        content = settings_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        if path is None:
            return Settings()
        raise SettingsError(f"Settings file not found: {settings_path}") from exc
    except (OSError, UnicodeError) as exc:
        raise SettingsError(f"Cannot read {settings_path}: {exc}") from exc

    try:
        data = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        raise SettingsError(f"Invalid YAML in {settings_path}: {exc}") from exc

    if data is None:
        return Settings()
    if not isinstance(data, dict):
        raise SettingsError(f"{settings_path} must contain a YAML mapping.")
    unknown = data.keys() - {"converter"}
    if unknown:
        names = ", ".join(sorted(str(key) for key in unknown))
        raise SettingsError(f"Unknown settings in {settings_path}: {names}")
    converter = data.get("converter", Converter.DOCLING.value)
    if not isinstance(converter, str):
        raise SettingsError("'converter' must be a string.")
    try:
        return Settings(converter=Converter(converter))
    except ValueError as exc:
        choices = ", ".join(Converter)
        message = f"Unknown converter {converter!r}. Choose: {choices}."
        raise SettingsError(message) from exc

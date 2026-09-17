"""Typed, dependency-free loading of local project settings."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

from .exceptions import ConfigurationError


@dataclass(frozen=True)
class Settings:
    """Resolved local settings; secrets deliberately do not live in this object."""

    project_root: Path
    database_path: Path
    raw_data_path: Path
    processed_data_path: Path
    log_directory: Path
    log_level: str


def load_settings(project_root: Path | None = None) -> Settings:
    """Load non-secret settings from ``config/settings.toml`` and environment."""
    root = (project_root or Path.cwd()).resolve()
    settings_path = root / "config" / "settings.toml"
    if not settings_path.is_file():
        raise ConfigurationError(f"Settings file not found: {settings_path}")

    with settings_path.open("rb") as settings_file:
        payload = tomllib.load(settings_file)

    try:
        paths = payload["paths"]
        configured_level = payload["logging"]["level"]
        return Settings(
            project_root=root,
            database_path=root / paths["database"],
            raw_data_path=root / paths["raw_data"],
            processed_data_path=root / paths["processed_data"],
            log_directory=root / paths["log_directory"],
            log_level=os.getenv("LOG_LEVEL", configured_level).upper(),
        )
    except (KeyError, TypeError) as error:
        raise ConfigurationError("config/settings.toml is missing a required setting") from error

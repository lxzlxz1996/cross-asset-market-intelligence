"""Project logging configuration."""

from __future__ import annotations

import logging

from .config import Settings


def configure_logging(settings: Settings) -> logging.Logger:
    """Configure the package logger without altering global application logging."""
    logger = logging.getLogger("cross_asset_market_intelligence")
    logger.setLevel(settings.log_level)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        logger.addHandler(handler)
    return logger

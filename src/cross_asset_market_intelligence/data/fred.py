"""FRED retrieval and parsing at the raw-observation boundary."""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from datetime import date
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from ..exceptions import ConfigurationError, SourceResponseError, SourceRetrievalError

FRED_OBSERVATIONS_URL = "https://api.stlouisfed.org/fred/series/observations"


@dataclass(frozen=True)
class FredObservation:
    """A validated FRED observation, including its source real-time period."""

    series_id: str
    observation_date: date
    value: float | None
    raw_value: str
    realtime_start: str
    realtime_end: str

    @property
    def vintage_key(self) -> str:
        """Stable key for FRED's date-level real-time availability interval."""
        return f"fred_realtime:{self.realtime_start}:{self.realtime_end}"


HttpGet = Callable[[str], bytes]


class FredClient:
    """Small official-FRED API client; it deliberately has no indicator mapping."""

    def __init__(self, api_key: str, http_get: HttpGet | None = None) -> None:
        if not api_key:
            raise ConfigurationError("FRED_API_KEY is required for FRED ingestion")
        self._api_key = api_key
        self._http_get = http_get or _http_get

    @classmethod
    def from_environment(cls, http_get: HttpGet | None = None) -> "FredClient":
        return cls(os.getenv("FRED_API_KEY", ""), http_get=http_get)

    def fetch_observations(
        self,
        series_id: str,
        *,
        observation_start: date | None = None,
        observation_end: date | None = None,
    ) -> list[FredObservation]:
        """Fetch and validate untransformed observations for a supplied FRED ID."""
        parameters = {
            "series_id": series_id,
            "api_key": self._api_key,
            "file_type": "json",
            "units": "lin",
        }
        if observation_start is not None:
            parameters["observation_start"] = observation_start.isoformat()
        if observation_end is not None:
            parameters["observation_end"] = observation_end.isoformat()

        url = f"{FRED_OBSERVATIONS_URL}?{urlencode(parameters)}"
        try:
            payload = json.loads(self._http_get(url).decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, OSError) as error:
            raise SourceRetrievalError(f"FRED request failed for {series_id}") from error
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise SourceResponseError(f"FRED returned malformed JSON for {series_id}") from error

        return parse_fred_observations(series_id, payload)


def parse_fred_observations(series_id: str, payload: Any) -> list[FredObservation]:
    """Parse FRED's documented observations payload without fabricating values."""
    if not isinstance(payload, dict) or not isinstance(payload.get("observations"), list):
        raise SourceResponseError("FRED response must contain an observations list")

    parsed: list[FredObservation] = []
    for item in payload["observations"]:
        if not isinstance(item, dict):
            raise SourceResponseError("FRED observations must be objects")
        try:
            observation_date = date.fromisoformat(_required_string(item, "date"))
            raw_value = _required_string(item, "value")
            realtime_start = _required_iso_date(item, "realtime_start")
            realtime_end = _required_iso_date(item, "realtime_end")
        except ValueError as error:
            raise SourceResponseError(f"Invalid FRED observation for {series_id}") from error

        if raw_value == ".":
            value = None
        else:
            try:
                value = float(raw_value)
            except ValueError as error:
                raise SourceResponseError(
                    f"FRED value for {series_id} on {observation_date} is not numeric"
                ) from error
            if not math.isfinite(value):
                raise SourceResponseError(
                    f"FRED value for {series_id} on {observation_date} is not finite"
                )

        parsed.append(
            FredObservation(
                series_id=series_id,
                observation_date=observation_date,
                value=value,
                raw_value=raw_value,
                realtime_start=realtime_start,
                realtime_end=realtime_end,
            )
        )
    return parsed


def _http_get(url: str) -> bytes:
    with urlopen(url, timeout=30) as response:  # nosec B310: fixed official FRED endpoint
        return response.read()


def _required_string(item: dict[str, Any], field: str) -> str:
    value = item.get(field)
    if not isinstance(value, str) or not value:
        raise ValueError(f"Missing or invalid {field}")
    return value


def _required_iso_date(item: dict[str, Any], field: str) -> str:
    value = _required_string(item, field)
    date.fromisoformat(value)
    return value

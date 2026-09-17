"""Official FRBNY SOFR retrieval and response validation at the raw boundary."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import date
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from ..exceptions import SourceResponseError, SourceRetrievalError

FRBNY_SOFR_SEARCH_URL = "https://markets.newyorkfed.org/api/rates/secured/sofr/search.json"
FRBNY_SOFR_LATEST_URL = "https://markets.newyorkfed.org/api/rates/secured/sofr/last/1.json"
FRBNY_SOURCE = "frbny"
FRBNY_SOFR_SERIES_ID = "SOFR"
FRBNY_SOFR_VINTAGE_PREFIX = "frbny_sofr_revision:"


@dataclass(frozen=True)
class FrbnySofrObservation:
    """One official FRBNY SOFR record, retaining its revision indicator."""

    effective_date: date
    percent_rate: float
    revision_indicator: str
    source_record: dict[str, object]

    @property
    def vintage_key(self) -> str:
        """Identify the official original or revised response state for one date."""
        return f"{FRBNY_SOFR_VINTAGE_PREFIX}{self.revision_indicator or 'original'}"


HttpGet = Callable[[str], bytes]


class FrbnySofrClient:
    """Small client for the official FRBNY SOFR API only."""

    def __init__(self, http_get: HttpGet | None = None) -> None:
        self._http_get = http_get or _http_get

    def fetch_observations(
        self,
        *,
        observation_start: date | None = None,
        observation_end: date | None = None,
    ) -> list[FrbnySofrObservation]:
        """Fetch either the latest SOFR rate or one explicitly bounded date range."""
        if (observation_start is None) != (observation_end is None):
            raise ValueError("FRBNY SOFR date range requires both start and end dates")
        if observation_start is None:
            url = FRBNY_SOFR_LATEST_URL
        else:
            url = f"{FRBNY_SOFR_SEARCH_URL}?{urlencode({
                'startDate': observation_start.isoformat(),
                'endDate': observation_end.isoformat(),
                'type': 'rate',
            })}"
        try:
            payload = json.loads(self._http_get(url).decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, OSError) as error:
            raise SourceRetrievalError("FRBNY SOFR request failed") from error
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise SourceResponseError("FRBNY SOFR returned malformed JSON") from error
        return parse_frbny_sofr_observations(payload)


def parse_frbny_sofr_observations(payload: Any) -> list[FrbnySofrObservation]:
    """Parse documented FRBNY ``refRates`` without fabricating observations."""
    if not isinstance(payload, dict) or not isinstance(payload.get("refRates"), list):
        raise SourceResponseError("FRBNY SOFR response must contain a refRates list")

    parsed: list[FrbnySofrObservation] = []
    for item in payload["refRates"]:
        if not isinstance(item, dict):
            raise SourceResponseError("FRBNY SOFR refRates must be objects")
        try:
            effective_date = date.fromisoformat(_required_string(item, "effectiveDate"))
            rate_type = _required_string(item, "type")
            revision_indicator = _required_string(item, "revisionIndicator", allow_empty=True)
            raw_percent_rate = item["percentRate"]
            if isinstance(raw_percent_rate, bool) or not isinstance(raw_percent_rate, (int, float)):
                raise ValueError("percentRate must be a JSON number")
            percent_rate = float(raw_percent_rate)
        except (KeyError, TypeError, ValueError) as error:
            raise SourceResponseError("Invalid FRBNY SOFR rate record") from error
        if rate_type != FRBNY_SOFR_SERIES_ID:
            raise SourceResponseError(f"FRBNY SOFR response returned unexpected rate type: {rate_type}")
        if not math.isfinite(percent_rate):
            raise SourceResponseError(f"FRBNY SOFR rate for {effective_date} is not finite")
        if not revision_indicator.isalnum() and revision_indicator:
            raise SourceResponseError("FRBNY SOFR revisionIndicator is malformed")

        parsed.append(
            FrbnySofrObservation(
                effective_date=effective_date,
                percent_rate=percent_rate,
                revision_indicator=revision_indicator,
                source_record=dict(item),
            )
        )
    return parsed


def _http_get(url: str) -> bytes:
    with urlopen(url, timeout=30) as response:  # nosec B310: fixed official FRBNY endpoints
        return response.read()


def _required_string(item: dict[str, Any], field: str, *, allow_empty: bool = False) -> str:
    value = item.get(field)
    if not isinstance(value, str) or (not allow_empty and not value):
        raise ValueError(f"Missing or invalid {field}")
    return value

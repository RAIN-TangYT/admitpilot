"""Official page fetching utilities for AIE."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Protocol
from urllib.parse import urlparse

from admitpilot.platform.common.time import utc_now


class OfficialPageFetchError(RuntimeError):
    """Base fetch failure."""


class DisallowedDomainError(OfficialPageFetchError):
    """Raised when target URL is outside the domain allowlist."""


class OfficialPageNotFoundError(OfficialPageFetchError):
    """Raised when the requested page does not exist."""


@dataclass(frozen=True, slots=True)
class HttpResponse:
    """Minimal HTTP response contract for page fetchers."""

    url: str
    status_code: int
    text: str
    headers: dict[str, str] = field(default_factory=dict)


class HttpClient(Protocol):
    """Minimal sync HTTP client contract."""

    def get(self, url: str, headers: Mapping[str, str], timeout: float) -> HttpResponse:
        """Fetch an URL and return a response."""


@dataclass(frozen=True, slots=True)
class OfficialPageSpec:
    """Metadata required to fetch one official page."""

    school: str
    program: str
    cycle: str
    page_type: str
    url: str
    allowed_domains: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FetchedOfficialPage:
    """Fetched official page payload with metadata."""

    spec: OfficialPageSpec
    content: str
    fetched_at: datetime
    status_code: int
    content_type: str
    mode: str


class FixtureHttpClient:
    """Read official pages from fixture files."""

    def __init__(self, fixtures: Mapping[str, Path] | Callable[[str], Path | None]) -> None:
        self._fixtures = fixtures

    def get(self, url: str, headers: Mapping[str, str], timeout: float) -> HttpResponse:
        del headers, timeout
        fixture_path = self._resolve_path(url)
        if fixture_path is None or not fixture_path.exists():
            raise OfficialPageNotFoundError(f"fixture page not found for url={url}")
        return HttpResponse(
            url=url,
            status_code=200,
            text=fixture_path.read_text(encoding="utf-8"),
            headers={"content-type": "text/html; charset=utf-8"},
        )

    def _resolve_path(self, url: str) -> Path | None:
        if callable(self._fixtures):
            return self._fixtures(url)
        return self._fixtures.get(url)


class LiveHttpClient:
    """Live HTTP client used outside fixture mode."""

    def get(self, url: str, headers: Mapping[str, str], timeout: float) -> HttpResponse:
        import httpx

        response = httpx.get(
            url,
            headers=dict(headers),
            timeout=timeout,
            follow_redirects=True,
        )
        response.raise_for_status()
        return HttpResponse(
            url=str(response.url),
            status_code=response.status_code,
            text=response.text,
            headers={key.lower(): value for key, value in response.headers.items()},
        )


class OfficialPageFetcher:
    """Fetch official pages with allowlist, timeout, and retry control."""

    def __init__(
        self,
        http_client: HttpClient,
        *,
        user_agent: str = "AdmitPilot/phase2",
        timeout_seconds: float = 5.0,
        max_retries: int = 1,
        mode: str = "fixture",
    ) -> None:
        self.http_client = http_client
        self.user_agent = user_agent
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.mode = mode

    def fetch(self, spec: OfficialPageSpec) -> FetchedOfficialPage:
        self._ensure_allowed(spec.url, spec.allowed_domains)
        last_error: Exception | None = None
        for _ in range(self.max_retries + 1):
            try:
                response = self.http_client.get(
                    spec.url,
                    headers={"User-Agent": self.user_agent},
                    timeout=self.timeout_seconds,
                )
                return FetchedOfficialPage(
                    spec=spec,
                    content=response.text,
                    fetched_at=utc_now(),
                    status_code=response.status_code,
                    content_type=response.headers.get("content-type", "text/html"),
                    mode=self.mode,
                )
            except OfficialPageFetchError as exc:
                last_error = exc
                break
            except Exception as exc:  # pragma: no cover - exercised in live mode only.
                last_error = exc
        raise OfficialPageFetchError(f"failed to fetch url={spec.url}") from last_error

    def fetch_many(self, specs: list[OfficialPageSpec]) -> list[FetchedOfficialPage]:
        return [self.fetch(spec) for spec in specs]

    def _ensure_allowed(self, url: str, allowed_domains: tuple[str, ...]) -> None:
        hostname = (urlparse(url).hostname or "").lower()
        if not hostname:
            raise DisallowedDomainError(f"missing hostname: {url}")
        if any(hostname == domain or hostname.endswith(f".{domain}") for domain in allowed_domains):
            return
        raise DisallowedDomainError(f"domain not allowed: {hostname}")

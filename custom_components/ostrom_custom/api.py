"""API client for the Ostrom REST and OAuth2 API."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
from typing import Any

import aiohttp

from .const import AUTH_URL, BASE_URL

_LOGGER = logging.getLogger(__name__)


class OstromError(Exception):
    """Base exception for Ostrom API errors."""


class OstromAuthError(OstromError):
    """Exception for authentication/authorization errors (401/403)."""


class OstromConnectionError(OstromError):
    """Exception for network connection and timeout errors."""


class OstromRateLimitError(OstromError):
    """Exception for API rate limit exceeded (429)."""


class OstromApiError(OstromError):
    """Exception for unexpected API response errors."""


class OstromApiClient:
    """Client to communicate with the Ostrom API."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        client_id: str,
        client_secret: str,
        zip_code: str,
    ) -> None:
        """Initialize the Ostrom API client."""
        self._session = session
        self.client_id = client_id
        self.client_secret = client_secret
        self.zip_code = zip_code
        self._access_token: str | None = None
        self._token_expiry: datetime | None = None

    async def async_get_access_token(self) -> str:
        """Retrieve an OAuth2 access token or reuse a valid cached one."""
        now = datetime.now(timezone.utc)
        if self._access_token and self._token_expiry and now < self._token_expiry:
            return self._access_token

        try:
            async with self._session.post(
                AUTH_URL,
                auth=aiohttp.BasicAuth(self.client_id, self.client_secret),
                data={"grant_type": "client_credentials"},
                headers={"Accept": "application/json"},
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status in (400, 401, 403):
                    raise OstromAuthError(
                        f"Ungültige Zugangsdaten für Ostrom API (HTTP {resp.status})"
                    )
                if resp.status == 429:
                    raise OstromRateLimitError(
                        "Ostrom API Ratenlimit erreicht (HTTP 429)"
                    )
                if resp.status not in (200, 201):
                    raise OstromApiError(
                        f"Unerwarteter HTTP-Status beim Token-Abruf: {resp.status}"
                    )

                data = await resp.json()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise OstromConnectionError(
                f"Verbindungsfehler beim Ostrom OAuth-Endpunkt: {err}"
            ) from err

        try:
            self._access_token = data["access_token"]
            expires_in = int(data.get("expires_in", 3600))
            if expires_in <= 0:
                raise ValueError("expires_in must be positive")
        except (KeyError, TypeError, ValueError) as err:
            raise OstromApiError("Ungültige Token-Antwort von Ostrom") from err

        self._token_expiry = datetime.now(timezone.utc) + timedelta(
            seconds=max(expires_in - 60, 0)
        )
        return self._access_token

    async def async_validate_credentials(self) -> bool:
        """Validate credentials by requesting a new token."""
        self._access_token = None
        self._token_expiry = None
        await self.async_get_access_token()
        return True

    async def _async_request(
        self, method: str, endpoint: str, params: dict[str, Any] | None = None
    ) -> Any:
        """Make an authenticated request to the Ostrom API."""
        token = await self.async_get_access_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }
        url = f"{BASE_URL}{endpoint}"

        try:
            async with self._session.request(
                method,
                url,
                headers=headers,
                params=params,
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                if resp.status == 401:
                    self._access_token = None
                    self._token_expiry = None
                    raise OstromAuthError("Ostrom Token abgelaufen oder ungültig")
                if resp.status == 429:
                    raise OstromRateLimitError("Ostrom API Ratenlimit erreicht (429)")
                if resp.status == 404:
                    return None
                if resp.status not in (200, 201):
                    raise OstromApiError(
                        f"Ostrom API Fehler auf {endpoint}: HTTP {resp.status}"
                    )
                return await resp.json()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise OstromConnectionError(
                f"Verbindungsfehler bei Ostrom API {endpoint}: {err}"
            ) from err

    async def async_get_spot_prices(
        self, start_date: datetime, end_date: datetime
    ) -> list[dict[str, Any]]:
        """Fetch spot price data for the specified date range."""
        params = {
            "startDate": start_date.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "endDate": end_date.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "resolution": "HOUR",
            "zip": self.zip_code,
        }
        result = await self._async_request("GET", "/spot-prices", params=params)
        if not result or "data" not in result:
            return []
        return result["data"]

    async def async_get_contracts(self) -> list[dict[str, Any]]:
        """Fetch electricity contracts for the user."""
        result = await self._async_request("GET", "/contracts")
        if not result or "data" not in result:
            return []
        return result["data"]

    async def async_get_energy_consumption(
        self, contract_id: int | str, start_date: datetime, end_date: datetime
    ) -> list[dict[str, Any]]:
        """Fetch smart meter energy consumption for a contract."""
        params = {
            "startDate": start_date.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "endDate": end_date.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            "resolution": "HOUR",
        }
        result = await self._async_request(
            "GET", f"/contracts/{contract_id}/energy-consumption", params=params
        )
        if not result or "data" not in result:
            return []
        return result["data"]

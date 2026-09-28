"""Tests for OstromApiClient."""
from __future__ import annotations

from datetime import datetime, timezone
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from tests.mock_ha import setup_mock_ha
setup_mock_ha()

from custom_components.ostrom_custom.api import (
    OstromApiClient,
    OstromAuthError,
    OstromConnectionError,
    OstromRateLimitError,
)


class MockResponse:
    def __init__(self, status: int, json_data: dict | list | None = None) -> None:
        self.status = status
        self._json_data = json_data

    async def json(self) -> dict | list | None:
        return self._json_data

    async def __aenter__(self) -> MockResponse:
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        pass


class TestOstromApiClient(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.session = MagicMock()
        self.client = OstromApiClient(
            session=self.session,
            client_id="test_client_id",
            client_secret="test_client_secret",
            zip_code="10115",
        )

    async def test_get_access_token_success(self) -> None:
        self.session.post.return_value = MockResponse(
            200, {"access_token": "token_abc123", "expires_in": 3600, "token_type": "Bearer"}
        )

        token = await self.client.async_get_access_token()
        self.assertEqual(token, "token_abc123")

        self.session.post.reset_mock()
        token2 = await self.client.async_get_access_token()
        self.assertEqual(token2, "token_abc123")
        self.session.post.assert_not_called()

    async def test_get_access_token_success_201(self) -> None:
        """Test successful token retrieval when Ostrom returns 201 Created."""
        self.session.post.return_value = MockResponse(
            201, {"access_token": "token_201_xyz", "expires_in": 3600, "token_type": "Bearer"}
        )
        token = await self.client.async_get_access_token()
        self.assertEqual(token, "token_201_xyz")

    async def test_get_access_token_invalid_auth(self) -> None:
        self.session.post.return_value = MockResponse(401, {"error": "invalid_client"})
        with self.assertRaises(OstromAuthError):
            await self.client.async_get_access_token()

    async def test_get_access_token_rate_limit(self) -> None:
        self.session.post.return_value = MockResponse(429, {"type": "too_many_requests"})
        with self.assertRaises(OstromRateLimitError):
            await self.client.async_get_access_token()

    async def test_get_spot_prices(self) -> None:
        self.client._access_token = "valid_token"
        self.client._token_expiry = datetime.max.replace(tzinfo=timezone.utc)

        fake_prices = [
            {
                "date": "2026-09-29T10:00:00.000Z",
                "grossKwhPrice": 25.5,
                "grossKwhTaxAndLevies": 12.0,
                "netKwhPrice": 21.4,
            }
        ]
        self.session.request.return_value = MockResponse(200, {"data": fake_prices})

        start = datetime(2026, 9, 29, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 9, 30, 0, 0, tzinfo=timezone.utc)
        res = await self.client.async_get_spot_prices(start, end)

        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["grossKwhPrice"], 25.5)

    async def test_get_contracts(self) -> None:
        self.client._access_token = "valid_token"
        self.client._token_expiry = datetime.max.replace(tzinfo=timezone.utc)

        fake_contracts = [
            {"id": "1001", "status": "ACTIVE", "productCode": "SIMPLY_DYNAMIC"}
        ]
        self.session.request.return_value = MockResponse(200, {"data": fake_contracts})

        res = await self.client.async_get_contracts()
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["id"], "1001")

    async def test_get_energy_consumption_not_found(self) -> None:
        self.client._access_token = "valid_token"
        self.client._token_expiry = datetime.max.replace(tzinfo=timezone.utc)

        self.session.request.return_value = MockResponse(404, None)

        start = datetime(2026, 9, 27, 0, 0, tzinfo=timezone.utc)
        end = datetime(2026, 9, 29, 0, 0, tzinfo=timezone.utc)
        res = await self.client.async_get_energy_consumption("1001", start, end)
        self.assertEqual(res, [])


if __name__ == "__main__":
    unittest.main()

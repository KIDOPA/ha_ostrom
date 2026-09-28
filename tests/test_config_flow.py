"""Tests for the Ostrom config flow."""
from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from tests.mock_ha import setup_mock_ha
setup_mock_ha()

from custom_components.ostrom_custom.api import (
    OstromAuthError,
    OstromConnectionError,
    OstromRateLimitError,
)
from custom_components.ostrom_custom.config_flow import OstromConfigFlow
from homeassistant.config_entries import AbortFlow


class TestOstromConfigFlow(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.flow = OstromConfigFlow()

    async def test_form_shown_on_empty_input(self) -> None:
        result = await self.flow.async_step_user(None)
        self.assertEqual(result["type"], "form")
        self.assertEqual(result["step_id"], "user")
        self.assertEqual(result["errors"], {})

    @patch("custom_components.ostrom_custom.config_flow.OstromApiClient")
    async def test_successful_config(self, mock_client_cls) -> None:
        mock_client = mock_client_cls.return_value
        mock_client.async_validate_credentials = AsyncMock(return_value=True)

        user_input = {
            "client_id": " my_client_id ",
            "client_secret": " secret123 ",
            "zip_code": " 10115 ",
        }

        result = await self.flow.async_step_user(user_input)

        self.assertEqual(result["type"], "create_entry")
        self.assertEqual(result["title"], "Ostrom (10115)")
        self.assertEqual(result["data"]["client_id"], "my_client_id")
        self.assertEqual(result["data"]["client_secret"], "secret123")
        self.assertEqual(result["data"]["zip_code"], "10115")

    @patch("custom_components.ostrom_custom.config_flow.OstromApiClient")
    async def test_invalid_auth_error(self, mock_client_cls) -> None:
        mock_client = mock_client_cls.return_value
        mock_client.async_validate_credentials = AsyncMock(
            side_effect=OstromAuthError("Invalid credentials")
        )

        user_input = {
            "client_id": "bad_id",
            "client_secret": "bad_secret",
            "zip_code": "10115",
        }

        result = await self.flow.async_step_user(user_input)

        self.assertEqual(result["type"], "form")
        self.assertEqual(result["errors"], {"base": "invalid_auth"})

    @patch("custom_components.ostrom_custom.config_flow.OstromApiClient")
    async def test_cannot_connect_error(self, mock_client_cls) -> None:
        mock_client = mock_client_cls.return_value
        mock_client.async_validate_credentials = AsyncMock(
            side_effect=OstromConnectionError("Timeout")
        )

        user_input = {
            "client_id": "id",
            "client_secret": "secret",
            "zip_code": "10115",
        }

        result = await self.flow.async_step_user(user_input)

        self.assertEqual(result["type"], "form")
        self.assertEqual(result["errors"], {"base": "cannot_connect"})

    @patch("custom_components.ostrom_custom.config_flow.OstromApiClient")
    async def test_rate_limited_error(self, mock_client_cls) -> None:
        mock_client = mock_client_cls.return_value
        mock_client.async_validate_credentials = AsyncMock(
            side_effect=OstromRateLimitError("Rate limit exceeded")
        )

        user_input = {
            "client_id": "id",
            "client_secret": "secret",
            "zip_code": "10115",
        }

        result = await self.flow.async_step_user(user_input)

        self.assertEqual(result["type"], "form")
        self.assertEqual(result["errors"], {"base": "rate_limited"})

    async def test_abort_if_already_configured(self) -> None:
        self.flow._abort_entries = ["existing_client_id"]
        user_input = {
            "client_id": "existing_client_id",
            "client_secret": "secret",
            "zip_code": "10115",
        }

        with self.assertRaises(AbortFlow):
            await self.flow.async_step_user(user_input)


if __name__ == "__main__":
    unittest.main()

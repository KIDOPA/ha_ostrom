"""Tests for integration setup and unload in __init__.py."""
from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from tests.mock_ha import setup_mock_ha
setup_mock_ha()

from custom_components.ostrom_custom import async_setup_entry, async_unload_entry
from custom_components.ostrom_custom.const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_ZIP_CODE,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


class TestIntegrationLifecycle(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.hass = HomeAssistant()
        self.entry = ConfigEntry(
            entry_id="test_entry_id",
            data={
                CONF_CLIENT_ID: "client123",
                CONF_CLIENT_SECRET: "secret123",
                CONF_ZIP_CODE: "10115",
            },
        )

    @patch("custom_components.ostrom_custom.OstromDataCoordinator")
    async def test_setup_and_unload_entry(self, mock_coord_cls) -> None:
        mock_coordinator = mock_coord_cls.return_value
        mock_coordinator.async_config_entry_first_refresh = AsyncMock()

        self.hass.config_entries.async_forward_entry_setups = AsyncMock(return_value=True)
        self.hass.config_entries.async_unload_platforms = AsyncMock(return_value=True)

        setup_ok = await async_setup_entry(self.hass, self.entry)
        self.assertTrue(setup_ok)
        self.assertIn(self.entry.entry_id, self.hass.data[DOMAIN])
        self.assertEqual(self.entry.runtime_data, mock_coordinator)
        mock_coordinator.async_config_entry_first_refresh.assert_awaited_once()

        unload_ok = await async_unload_entry(self.hass, self.entry)
        self.assertTrue(unload_ok)
        self.assertNotIn(self.entry.entry_id, self.hass.data[DOMAIN])


if __name__ == "__main__":
    unittest.main()

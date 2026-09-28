"""Tests for OstromDataCoordinator."""
from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

from tests.mock_ha import setup_mock_ha
setup_mock_ha()

from custom_components.ostrom_custom.coordinator import (
    OstromData,
    OstromDataCoordinator,
)
from homeassistant.core import HomeAssistant


class TestOstromDataCoordinator(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.hass = HomeAssistant()
        self.hass.config.time_zone = "UTC"
        self.coordinator = OstromDataCoordinator(
            hass=self.hass,
            client_id="test_client",
            client_secret="test_secret",
            zip_code="10115",
        )

    def test_process_all_prices_and_rank(self) -> None:
        local_tz = ZoneInfo("UTC")
        now_utc = datetime(2026, 9, 29, 12, 30, tzinfo=timezone.utc)

        spot_data = []
        for h in range(24):
            spot_data.append(
                {
                    "date": f"2026-09-29T{h:02d}:00:00.000Z",
                    "grossKwhPrice": 10.0 + h,
                    "grossKwhTaxAndLevies": 10.0,
                    "netKwhPrice": 8.0,
                    "grossMonthlyOstromBaseFee": 6.00,
                    "grossMonthlyGridFees": 4.50,
                }
            )

        for h in range(3):
            spot_data.append(
                {
                    "date": f"2026-09-30T{h:02d}:00:00.000Z",
                    "grossKwhPrice": 15.0,
                    "grossKwhTaxAndLevies": 10.0,
                    "netKwhPrice": 12.0,
                    "grossMonthlyOstromBaseFee": 6.00,
                    "grossMonthlyGridFees": 4.50,
                }
            )

        consumption_data = [
            {"date": "2026-09-29T10:00:00.000Z", "kWh": 1.5},
            {"date": "2026-09-29T11:00:00.000Z", "kWh": 2.0},
        ]

        data: OstromData = self.coordinator._process_all(
            spot_data=spot_data,
            consumption_data=consumption_data,
            local_tz=local_tz,
            now_utc=now_utc,
        )

        self.assertAlmostEqual(data.current_price, 0.32, places=4)
        self.assertEqual(data.current_gross_kwh_price, 22.0)
        self.assertEqual(data.current_gross_tax_and_levies, 10.0)
        self.assertAlmostEqual(data.next_hour_price, 0.33, places=4)
        self.assertEqual(len(data.prices_today), 24)
        self.assertEqual(len(data.prices_tomorrow), 3)

        self.assertEqual(data.gross_monthly_ostrom_fee, 6.00)
        self.assertEqual(data.gross_monthly_grid_fee, 4.50)
        self.assertEqual(data.gross_monthly_base_fee, 10.50)
        self.assertAlmostEqual(data.daily_base_fee, 0.345, places=3)

        self.assertAlmostEqual(data.min_today, 0.20, places=4)
        self.assertAlmostEqual(data.max_today, 0.43, places=4)
        self.assertEqual(data.rank, 13)

        self.assertAlmostEqual(data.energy_consumption_today, 3.5, places=3)
        self.assertAlmostEqual(data.accrued_cost_today, 1.07, places=2)
        self.assertAlmostEqual(data.total_cost_today_with_base_fee, 1.42, places=2)

    def test_price_level_thresholds(self) -> None:
        local_tz = ZoneInfo("UTC")
        now_utc = datetime(2026, 9, 29, 0, 30, tzinfo=timezone.utc)

        spot_data = [
            {"date": "2026-09-29T00:00:00.000Z", "grossKwhPrice": 10.0, "grossKwhTaxAndLevies": 10.0},
            {"date": "2026-09-29T01:00:00.000Z", "grossKwhPrice": 30.0, "grossKwhTaxAndLevies": 10.0},
        ]
        data = self.coordinator._process_all(spot_data, [], local_tz, now_utc)
        self.assertEqual(data.price_level, "sehr_guenstig")


if __name__ == "__main__":
    unittest.main()

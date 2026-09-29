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

        # Historische Spotpreise für gestern (28.) und 48h (27.)
        spot_data.append(
            {
                "date": "2026-09-28T10:00:00.000Z",
                "grossKwhPrice": 12.0,
                "grossKwhTaxAndLevies": 10.0,
            }
        )
        spot_data.append(
            {
                "date": "2026-09-27T10:00:00.000Z",
                "grossKwhPrice": 14.0,
                "grossKwhTaxAndLevies": 10.0,
            }
        )

        consumption_data = [
            {"date": "2026-09-29T10:00:00.000Z", "kWh": 1.5},
            {"date": "2026-09-29T11:00:00.000Z", "kWh": 2.0},
            {"date": "2026-09-28T10:00:00.000Z", "kWh": 5.0},
            {"date": "2026-09-27T10:00:00.000Z", "kWh": 10.0},
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
        self.assertEqual(len(data.forecast), 27)

        # Min / Max Uhrzeit heute
        self.assertEqual(data.min_price_time_today, "00:00")
        self.assertEqual(data.max_price_time_today, "23:00")

        # Fixkosten
        self.assertEqual(data.gross_monthly_ostrom_fee, 6.00)
        self.assertEqual(data.gross_monthly_grid_fee, 4.50)
        self.assertEqual(data.gross_monthly_base_fee, 10.50)
        self.assertEqual(data.daily_base_fee, 0.35)

        self.assertAlmostEqual(data.min_today, 0.20, places=4)
        self.assertAlmostEqual(data.max_today, 0.43, places=4)
        self.assertEqual(data.rank, 13)

        self.assertAlmostEqual(data.energy_consumption_today, 3.5, places=3)
        self.assertAlmostEqual(data.accrued_cost_today, 1.07, places=2)
        self.assertAlmostEqual(data.total_cost_today_with_base_fee, 1.42, places=2)

        # Gestern
        self.assertAlmostEqual(data.energy_consumption_yesterday, 5.0, places=3)
        self.assertAlmostEqual(data.accrued_cost_yesterday, 1.10, places=2)
        self.assertAlmostEqual(data.total_cost_yesterday_with_base_fee, 1.45, places=2)
        self.assertEqual(data.market_cost_yesterday, 0.60)
        self.assertEqual(data.tax_cost_yesterday, 0.50)
        self.assertEqual(len(data.hourly_breakdown_yesterday), 1)
        self.assertEqual(data.yesterday_date, "2026-09-28")

        # Vor 48h
        self.assertAlmostEqual(data.energy_consumption_48h, 10.0, places=3)
        self.assertAlmostEqual(data.accrued_cost_48h, 2.40, places=2)
        self.assertAlmostEqual(data.total_cost_48h_with_base_fee, 2.75, places=2)
        self.assertEqual(data.market_cost_48h, 1.40)
        self.assertEqual(data.tax_cost_48h, 1.00)
        self.assertEqual(len(data.hourly_breakdown_48h), 1)
        self.assertEqual(data.date_48h, "2026-09-27")

    def test_exact_cost_breakdown_scenario(self) -> None:
        """Verifiziert das exakte Zusammenspiel von Marktpreis, Abgaben und Grundpreis."""
        local_tz = ZoneInfo("Europe/Berlin")
        now_utc = datetime(2026, 9, 29, 12, 0, tzinfo=timezone.utc)

        spot_data = [
            {
                "date": "2026-09-28T14:00:00.000Z",
                "grossKwhPrice": 20.0617,
                "grossKwhTaxAndLevies": 17.0782,
                "grossMonthlyOstromBaseFee": 14.94,
                "grossMonthlyGridFees": 0.0,
            }
        ]
        consumption_data = [
            {"date": "2026-09-28T14:00:00.000Z", "kWh": 9.72},
        ]

        data = self.coordinator._process_all(
            spot_data=spot_data,
            consumption_data=consumption_data,
            local_tz=local_tz,
            now_utc=now_utc,
        )

        self.assertEqual(data.energy_consumption_yesterday, 9.72)
        self.assertEqual(data.daily_base_fee, 0.50)
        self.assertAlmostEqual(data.market_cost_yesterday, 1.95, places=2)
        self.assertAlmostEqual(data.tax_cost_yesterday, 1.66, places=2)
        self.assertAlmostEqual(data.accrued_cost_yesterday, 3.61, places=2)
        self.assertAlmostEqual(data.total_cost_yesterday_with_base_fee, 4.11, places=2)
        self.assertEqual(len(data.hourly_breakdown_yesterday), 1)
        self.assertEqual(data.hourly_breakdown_yesterday[0]["uhrzeit"], "16:00 - 17:00")
        self.assertEqual(data.hourly_breakdown_yesterday[0]["verbrauch_kwh"], 9.72)

    def test_timezone_day_boundary_aggregation(self) -> None:
        """Testet, dass UTC-Verbrauchsdaten gemäß deutscher Zeitzone (CEST, UTC+2) den richtigen Kalendertagen zugeordnet werden."""
        local_tz = ZoneInfo("Europe/Berlin")
        # 29. September 12:00 UTC (heute)
        now_utc = datetime(2026, 9, 29, 12, 0, tzinfo=timezone.utc)

        spot_data = [
            # 27. Sep 00:00 CEST -> 26. Sep 22:00 UTC
            {"date": "2026-09-26T22:00:00.000Z", "grossKwhPrice": 10.0, "grossKwhTaxAndLevies": 10.0},
            # 28. Sep 00:00 CEST -> 27. Sep 22:00 UTC
            {"date": "2026-09-27T22:00:00.000Z", "grossKwhPrice": 10.0, "grossKwhTaxAndLevies": 10.0},
            # 28. Sep 23:00 CEST -> 28. Sep 21:00 UTC
            {"date": "2026-09-28T21:00:00.000Z", "grossKwhPrice": 10.0, "grossKwhTaxAndLevies": 10.0},
            # 29. Sep 00:00 CEST -> 28. Sep 22:00 UTC
            {"date": "2026-09-28T22:00:00.000Z", "grossKwhPrice": 10.0, "grossKwhTaxAndLevies": 10.0},
        ]

        consumption_data = [
            # Vorgestern (27. Sep): Erste Stunde (00:00 CEST = 26. Sep 22:00 UTC)
            {"date": "2026-09-26T22:00:00.000Z", "kWh": 1.37},
            # Gestern (28. Sep): Erste Stunde (00:00 CEST = 27. Sep 22:00 UTC)
            {"date": "2026-09-27T22:00:00.000Z", "kWh": 0.51},
            # Gestern (28. Sep): Letzte Stunde (23:00 CEST = 28. Sep 21:00 UTC)
            {"date": "2026-09-28T21:00:00.000Z", "kWh": 9.21},
            # Heute (29. Sep): Erste Stunde (00:00 CEST = 28. Sep 22:00 UTC)
            {"date": "2026-09-28T22:00:00.000Z", "kWh": 0.40},
        ]

        data = self.coordinator._process_all(
            spot_data=spot_data,
            consumption_data=consumption_data,
            local_tz=local_tz,
            now_utc=now_utc,
        )

        # Vorgestern: 1.37 kWh
        self.assertEqual(data.energy_consumption_48h, 1.37)
        # Gestern: 0.51 + 9.21 = 9.72 kWh (exakt alle 24h des deutschen Kalendertags)
        self.assertEqual(data.energy_consumption_yesterday, 9.72)
        # Heute: 0.40 kWh
        self.assertEqual(data.energy_consumption_today, 0.4)

        # Überprüfe Uhrzeiten in lokaler Zeitzone
        self.assertEqual(data.hourly_breakdown_yesterday[0]["uhrzeit"], "00:00 - 01:00")
        self.assertEqual(data.hourly_breakdown_yesterday[1]["uhrzeit"], "23:00 - 00:00")

    def test_daily_and_hourly_base_fee_per_month(self) -> None:
        """Testet, dass die 14.94 EUR monatliche Grundgebühr exakt durch die Monatstage und Monatsstunden geteilt wird."""
        local_tz = ZoneInfo("Europe/Berlin")

        # 1. August (31 Tage)
        now_utc_august = datetime(2026, 8, 20, 12, 0, tzinfo=timezone.utc)
        spot_data_august = [
            {
                "date": "2026-08-20T10:00:00.000Z",
                "grossKwhPrice": 10.0,
                "grossKwhTaxAndLevies": 10.0,
                "grossMonthlyOstromBaseFee": 14.94,
                "grossMonthlyGridFees": 0.0,
            }
        ]
        data_august = self.coordinator._process_all(
            spot_data=spot_data_august,
            consumption_data=[],
            local_tz=local_tz,
            now_utc=now_utc_august,
        )
        # 14.94 / 31 = 0.4819... -> 0.49 EUR / Tag
        self.assertEqual(data_august.daily_base_fee, 0.49)
        # 14.94 / (31 * 24) = 0.02008 EUR / Stunde
        self.assertEqual(data_august.hourly_base_fee_today, 0.02008)

        # 2. September (30 Tage)
        now_utc_september = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)
        spot_data_september = [
            {
                "date": "2026-09-20T10:00:00.000Z",
                "grossKwhPrice": 10.0,
                "grossKwhTaxAndLevies": 10.0,
                "grossMonthlyOstromBaseFee": 14.94,
                "grossMonthlyGridFees": 0.0,
            }
        ]
        data_september = self.coordinator._process_all(
            spot_data=spot_data_september,
            consumption_data=[],
            local_tz=local_tz,
            now_utc=now_utc_september,
        )
        # 14.94 / 30 = 0.498 -> 0.50 EUR / Tag
        self.assertEqual(data_september.daily_base_fee, 0.50)
        # 14.94 / (30 * 24) = 0.02075 EUR / Stunde
        self.assertEqual(data_september.hourly_base_fee_today, 0.02075)


if __name__ == "__main__":
    unittest.main()


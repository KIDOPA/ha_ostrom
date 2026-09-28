"""Tests for Ostrom sensors."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from tests.mock_ha import setup_mock_ha
setup_mock_ha()

from custom_components.ostrom_custom.const import DOMAIN
from custom_components.ostrom_custom.coordinator import OstromData
from custom_components.ostrom_custom.sensor import (
    OstromAccruedCostSensor,
    OstromBaseFeeSensor,
    OstromConsumptionTodaySensor,
    OstromCurrentPriceSensor,
    OstromPriceLevelSensor,
    OstromRankSensor,
    async_setup_entry,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


class TestOstromSensors(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.hass = HomeAssistant()
        self.entry = ConfigEntry(
            entry_id="test_entry_123",
            data={"zip_code": "10115"},
        )
        self.coordinator = MagicMock()
        self.coordinator.zip_code = "10115"
        self.coordinator.data = OstromData(
            current_price=0.285,
            next_hour_price=0.291,
            avg_today=0.270,
            min_today=0.210,
            max_today=0.350,
            current_gross_kwh_price=16.5,
            current_gross_tax_and_levies=12.0,
            gross_monthly_ostrom_fee=6.0,
            gross_monthly_grid_fee=4.5,
            gross_monthly_base_fee=10.5,
            daily_base_fee=0.345,
            price_level="normal",
            rank=5,
            accrued_cost_today=1.45,
            total_cost_today_with_base_fee=1.80,
            energy_consumption_today=4.8,
            prices_today=[{"timestamp": "2026-09-29T12:00:00", "price": 0.285}],
            prices_tomorrow=[{"timestamp": "2026-09-30T12:00:00", "price": 0.275}],
        )
        self.entry.runtime_data = self.coordinator

    async def test_async_setup_entry(self) -> None:
        added_entities = []

        def async_add_entities(entities) -> None:
            added_entities.extend(entities)

        await async_setup_entry(self.hass, self.entry, async_add_entities)

        self.assertEqual(len(added_entities), 7)
        entity_classes = [e.__class__.__name__ for e in added_entities]
        self.assertIn("OstromCurrentPriceSensor", entity_classes)
        self.assertIn("OstromBaseFeeSensor", entity_classes)
        self.assertIn("OstromPriceLevelSensor", entity_classes)
        self.assertIn("OstromRankSensor", entity_classes)
        self.assertIn("OstromAccruedCostSensor", entity_classes)
        self.assertIn("OstromConsumptionTodaySensor", entity_classes)
        self.assertIn("OstromMeterReadingSensor", entity_classes)

    def test_current_price_sensor(self) -> None:
        sensor = OstromCurrentPriceSensor(self.coordinator, self.entry)

        self.assertEqual(sensor.native_value, 0.285)
        self.assertEqual(sensor.unique_id, "test_entry_123_current_price")
        self.assertEqual(sensor.device_class, "monetary")
        self.assertEqual(sensor.native_unit_of_measurement, "EUR/kWh")

        attrs = sensor.extra_state_attributes
        self.assertEqual(attrs["arbeitspreis_gesamt_ct_kwh"], 28.5)
        self.assertEqual(attrs["boersenpreis_brutto_ct_kwh"], 16.5)
        self.assertEqual(attrs["steuern_abgaben_netzentgelte_brutto_ct_kwh"], 12.0)
        self.assertEqual(attrs["naechste_stunde_eur_kwh"], 0.291)
        self.assertEqual(attrs["durchschnitt_heute_eur_kwh"], 0.270)
        self.assertEqual(len(attrs["preise_heute"]), 1)
        self.assertEqual(len(attrs["preise_morgen"]), 1)

        dev_info = sensor.device_info
        self.assertIn((DOMAIN, "test_entry_123"), dev_info.identifiers)
        self.assertEqual(dev_info.manufacturer, "Ostrom")

    def test_base_fee_sensor(self) -> None:
        sensor = OstromBaseFeeSensor(self.coordinator, self.entry)

        self.assertEqual(sensor.native_value, 10.5)
        self.assertEqual(sensor.unique_id, "test_entry_123_monthly_base_fee")
        self.assertEqual(sensor.device_class, "monetary")
        self.assertEqual(sensor.native_unit_of_measurement, "EUR")

        attrs = sensor.extra_state_attributes
        self.assertEqual(attrs["ostrom_grundgebuehr_monat"], 6.0)
        self.assertEqual(attrs["netzentgelte_grundgebuehr_monat"], 4.5)
        self.assertEqual(attrs["anteilige_grundgebuehr_pro_tag"], 0.345)

    def test_price_level_and_rank_sensors(self) -> None:
        level_sensor = OstromPriceLevelSensor(self.coordinator, self.entry)
        self.assertEqual(level_sensor.native_value, "normal")
        self.assertEqual(level_sensor.unique_id, "test_entry_123_price_level")

        rank_sensor = OstromRankSensor(self.coordinator, self.entry)
        self.assertEqual(rank_sensor.native_value, 5)
        self.assertEqual(rank_sensor.unique_id, "test_entry_123_price_rank")
        self.assertEqual(rank_sensor.extra_state_attributes["anzahl_stunden_heute"], 1)

    def test_accrued_cost_and_consumption_sensors(self) -> None:
        cost_sensor = OstromAccruedCostSensor(self.coordinator, self.entry)
        self.assertEqual(cost_sensor.native_value, 1.45)
        self.assertEqual(cost_sensor.unique_id, "test_entry_123_accrued_cost_today")
        self.assertEqual(cost_sensor.extra_state_attributes["anteilige_grundgebuehr_heute"], 0.345)
        self.assertEqual(cost_sensor.extra_state_attributes["gesamtkosten_heute_inkl_grundgebuehr"], 1.80)

        cons_sensor = OstromConsumptionTodaySensor(self.coordinator, self.entry)
        self.assertEqual(cons_sensor.native_value, 4.8)
        self.assertEqual(cons_sensor.unique_id, "test_entry_123_energy_consumption_today")


if __name__ == "__main__":
    unittest.main()

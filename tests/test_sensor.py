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
    OstromAccruedCostYesterdaySensor,
    OstromAccruedCost48hSensor,
    OstromAvgTodaySensor,
    OstromAvgTomorrowSensor,
    OstromBaseFeeSensor,
    OstromConsumptionTodaySensor,
    OstromConsumptionYesterdaySensor,
    OstromConsumption48hSensor,
    OstromCurrentPriceSensor,
    OstromHighestPriceTimeTodaySensor,
    OstromLowestPriceTimeTodaySensor,
    OstromLowestPriceTimeTomorrowSensor,
    OstromMaxTodaySensor,
    OstromMaxTomorrowSensor,
    OstromHighestPriceTimeTomorrowSensor,
    OstromMinTodaySensor,
    OstromMinTomorrowSensor,
    OstromNextHourPriceSensor,
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
            min_price_time_today="03:00",
            max_price_time_today="19:00",
            avg_tomorrow=0.265,
            min_tomorrow=0.195,
            max_tomorrow=0.330,
            min_price_time_tomorrow="04:00",
            max_price_time_tomorrow="18:00",
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
            accrued_cost_yesterday=2.34,
            total_cost_yesterday_with_base_fee=2.68,
            energy_consumption_yesterday=7.5,
            yesterday_date="2026-09-28",
            accrued_cost_48h=3.10,
            total_cost_48h_with_base_fee=3.45,
            energy_consumption_48h=9.2,
            date_48h="2026-09-27",
            prices_today=[{"timestamp": "2026-09-29T12:00:00", "price": 0.285}],
            prices_tomorrow=[{"timestamp": "2026-09-30T12:00:00", "price": 0.275}],
            forecast=[
                {"start": "2026-09-29T12:00:00", "end": "2026-09-29T13:00:00", "value": 0.285, "price": 0.285}
            ],
        )
        self.entry.runtime_data = self.coordinator

    async def test_async_setup_entry(self) -> None:
        added_entities = []

        def async_add_entities(entities) -> None:
            added_entities.extend(entities)

        await async_setup_entry(self.hass, self.entry, async_add_entities)

        self.assertEqual(len(added_entities), 22)
        entity_classes = [e.__class__.__name__ for e in added_entities]
        self.assertIn("OstromCurrentPriceSensor", entity_classes)
        self.assertIn("OstromNextHourPriceSensor", entity_classes)
        self.assertIn("OstromAvgTodaySensor", entity_classes)
        self.assertIn("OstromMinTodaySensor", entity_classes)
        self.assertIn("OstromLowestPriceTimeTodaySensor", entity_classes)
        self.assertIn("OstromMaxTodaySensor", entity_classes)
        self.assertIn("OstromHighestPriceTimeTodaySensor", entity_classes)
        self.assertIn("OstromAvgTomorrowSensor", entity_classes)
        self.assertIn("OstromMinTomorrowSensor", entity_classes)
        self.assertIn("OstromLowestPriceTimeTomorrowSensor", entity_classes)
        self.assertIn("OstromMaxTomorrowSensor", entity_classes)
        self.assertIn("OstromHighestPriceTimeTomorrowSensor", entity_classes)
        self.assertIn("OstromAccruedCostYesterdaySensor", entity_classes)
        self.assertIn("OstromConsumptionYesterdaySensor", entity_classes)
        self.assertIn("OstromAccruedCost48hSensor", entity_classes)
        self.assertIn("OstromConsumption48hSensor", entity_classes)

    def test_forecast_and_future_sensors(self) -> None:
        sensor_current = OstromCurrentPriceSensor(self.coordinator, self.entry)
        self.assertEqual(sensor_current.native_value, 0.285)
        self.assertIn("forecast", sensor_current.extra_state_attributes)

        sensor_next = OstromNextHourPriceSensor(self.coordinator, self.entry)
        self.assertEqual(sensor_next.native_value, 0.291)

        sensor_min_time = OstromLowestPriceTimeTodaySensor(self.coordinator, self.entry)
        self.assertEqual(sensor_min_time.native_value, "03:00")

        sensor_max_time = OstromHighestPriceTimeTodaySensor(self.coordinator, self.entry)
        self.assertEqual(sensor_max_time.native_value, "19:00")

        sensor_min_tomorrow = OstromMinTomorrowSensor(self.coordinator, self.entry)
        self.assertEqual(sensor_min_tomorrow.native_value, 0.195)

        sensor_max_tomorrow_time = OstromHighestPriceTimeTomorrowSensor(self.coordinator, self.entry)
        self.assertEqual(sensor_max_tomorrow_time.native_value, "18:00")

        sensor_cost_yesterday = OstromAccruedCostYesterdaySensor(self.coordinator, self.entry)
        self.assertEqual(sensor_cost_yesterday.native_value, 2.68)
        self.assertEqual(sensor_cost_yesterday.extra_state_attributes["reine_verbrauchskosten_gestern"], 2.34)
        self.assertEqual(sensor_cost_yesterday.extra_state_attributes["gesamtkosten_gestern_inkl_grundgebuehr"], 2.68)

        sensor_kwh_48h = OstromConsumption48hSensor(self.coordinator, self.entry)
        self.assertEqual(sensor_kwh_48h.native_value, 9.2)


if __name__ == "__main__":
    unittest.main()
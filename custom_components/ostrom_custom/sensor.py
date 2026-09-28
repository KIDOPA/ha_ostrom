"""Sensor-Plattform für erweiterte Ostrom-Metriken."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import OstromDataCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Richtet Ostrom-Sensoren aus einem ConfigEntry ein."""
    coordinator: OstromDataCoordinator = (
        entry.runtime_data
        if hasattr(entry, "runtime_data") and entry.runtime_data is not None
        else hass.data[DOMAIN][entry.entry_id]
    )

    async_add_entities(
        [
            OstromCurrentPriceSensor(coordinator, entry),
            OstromBaseFeeSensor(coordinator, entry),
            OstromPriceLevelSensor(coordinator, entry),
            OstromRankSensor(coordinator, entry),
            OstromAccruedCostSensor(coordinator, entry),
            OstromConsumptionTodaySensor(coordinator, entry),
            OstromMeterReadingSensor(coordinator, entry),
        ]
    )


class OstromBaseSensor(CoordinatorEntity[OstromDataCoordinator], SensorEntity):
    """Basisklasse für alle Ostrom-Sensoren mit DeviceInfo und eindeutiger ID."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: OstromDataCoordinator, entry: ConfigEntry) -> None:
        """Initialisiert den Basissensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._entry_id = entry.entry_id

    @property
    def device_info(self) -> DeviceInfo:
        """Verknüpft die Entität mit dem Ostrom-Gerät im Geräteregister."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry_id)},
            name=f"Ostrom ({self.coordinator.zip_code})",
            manufacturer="Ostrom",
            model="Smart Energy API",
            entry_type=DeviceEntryType.SERVICE,
        )


class OstromCurrentPriceSensor(OstromBaseSensor):
    """Aktueller Strompreis (Brutto inklusive Steuern, Abgaben und Netzentgelten)."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = "EUR/kWh"
    _attr_icon = "mdi:cash-fast"

    def __init__(self, coordinator: OstromDataCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_name = "Aktueller Strompreis"
        self._attr_unique_id = f"{self._entry_id}_current_price"

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.current_price

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        boersenpreis = self.coordinator.data.current_gross_kwh_price
        steuern_abgaben = self.coordinator.data.current_gross_tax_and_levies
        gesamt_ct = (
            round(boersenpreis + steuern_abgaben, 2)
            if boersenpreis is not None and steuern_abgaben is not None
            else None
        )

        return {
            "arbeitspreis_gesamt_ct_kwh": gesamt_ct,
            "boersenpreis_brutto_ct_kwh": boersenpreis,
            "steuern_abgaben_netzentgelte_brutto_ct_kwh": steuern_abgaben,
            "naechste_stunde_eur_kwh": self.coordinator.data.next_hour_price,
            "durchschnitt_heute_eur_kwh": self.coordinator.data.avg_today,
            "minimum_heute_eur_kwh": self.coordinator.data.min_today,
            "maximum_heute_eur_kwh": self.coordinator.data.max_today,
            "preise_heute": self.coordinator.data.prices_today,
            "preise_morgen": self.coordinator.data.prices_tomorrow,
        }


class OstromBaseFeeSensor(OstromBaseSensor):
    """Monatliche fixe Grundgebühren (Ostrom-Grundgebühr + Netzentgelte des Netzbetreibers)."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = "EUR"
    _attr_icon = "mdi:home-lightning-bolt"

    def __init__(self, coordinator: OstromDataCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_name = "Monatliche Grundgebühr"
        self._attr_unique_id = f"{self._entry_id}_monthly_base_fee"

    @property
    def native_value(self) -> float:
        return self.coordinator.data.gross_monthly_base_fee

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "ostrom_grundgebuehr_monat": self.coordinator.data.gross_monthly_ostrom_fee,
            "netzentgelte_grundgebuehr_monat": self.coordinator.data.gross_monthly_grid_fee,
            "anteilige_grundgebuehr_pro_tag": self.coordinator.data.daily_base_fee,
        }


class OstromPriceLevelSensor(OstromBaseSensor):
    """Zeigt an, ob Strom gerade 'sehr_guenstig', 'guenstig', 'normal', 'teuer' oder 'sehr_teuer' ist."""

    _attr_icon = "mdi:tag-outline"

    def __init__(self, coordinator: OstromDataCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_name = "Preisstufe"
        self._attr_unique_id = f"{self._entry_id}_price_level"

    @property
    def native_value(self) -> str:
        return self.coordinator.data.price_level

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "durchschnitt_heute": self.coordinator.data.avg_today,
            "minimum_heute": self.coordinator.data.min_today,
            "maximum_heute": self.coordinator.data.max_today,
        }


class OstromRankSensor(OstromBaseSensor):
    """Gibt den Rang der aktuellen Stunde an (1 = günstigste Stunde des Tages)."""

    _attr_icon = "mdi:format-list-numbered"

    def __init__(self, coordinator: OstromDataCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_name = "Preis Rang heute"
        self._attr_unique_id = f"{self._entry_id}_price_rank"

    @property
    def native_value(self) -> int | None:
        return self.coordinator.data.rank

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "anzahl_stunden_heute": len(self.coordinator.data.prices_today),
        }


class OstromAccruedCostSensor(OstromBaseSensor):
    """Tatsächlich aufgelaufene Stromkosten für den heutigen Tag."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = "EUR"
    _attr_icon = "mdi:currency-eur"

    def __init__(self, coordinator: OstromDataCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_name = "Stromkosten heute"
        self._attr_unique_id = f"{self._entry_id}_accrued_cost_today"

    @property
    def native_value(self) -> float:
        return self.coordinator.data.accrued_cost_today

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "reine_verbrauchskosten_heute": self.coordinator.data.accrued_cost_today,
            "anteilige_grundgebuehr_heute": self.coordinator.data.daily_base_fee,
            "gesamtkosten_heute_inkl_grundgebuehr": self.coordinator.data.total_cost_today_with_base_fee,
        }


class OstromConsumptionTodaySensor(OstromBaseSensor):
    """Tatsächlich gemessener Stromverbrauch des heutigen Tages über das Smart Meter."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_icon = "mdi:flash"

    def __init__(self, coordinator: OstromDataCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_name = "Stromverbrauch heute"
        self._attr_unique_id = f"{self._entry_id}_energy_consumption_today"

    @property
    def native_value(self) -> float:
        return self.coordinator.data.energy_consumption_today


class OstromMeterReadingSensor(OstromBaseSensor):
    """Zählerstand (falls vom Smart Meter geliefert)."""

    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_icon = "mdi:counter"

    def __init__(self, coordinator: OstromDataCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_name = "Zählerstand"
        self._attr_unique_id = f"{self._entry_id}_meter_reading"

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.meter_reading

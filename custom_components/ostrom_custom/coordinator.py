"""DataUpdateCoordinator für Ostrom mit Preisen, Verträgen und Verbrauch."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time, timedelta, timezone
import logging
from typing import Any
from zoneinfo import ZoneInfo

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    OstromApiClient,
    OstromAuthError,
    OstromConnectionError,
    OstromError,
    OstromRateLimitError,
)
from .const import DEFAULT_SCAN_INTERVAL_MINUTES

_LOGGER = logging.getLogger(__name__)


@dataclass
class OstromData:
    """Datenstruktur für alle Ostrom-Werte."""

    # Arbeitspreis aktuell & nächste Stunde (EUR/kWh)
    current_price: float | None = None
    next_hour_price: float | None = None

    # Preis-Statistiken heute
    avg_today: float = 0.0
    min_today: float = 0.0
    max_today: float = 0.0
    min_price_time_today: str | None = None
    max_price_time_today: str | None = None

    # Preis-Statistiken morgen (sobald verfügbar)
    avg_tomorrow: float | None = None
    min_tomorrow: float | None = None
    max_tomorrow: float | None = None
    min_price_time_tomorrow: str | None = None
    max_price_time_tomorrow: str | None = None

    # Preisbestandteile aktuell (Cent/kWh)
    current_gross_kwh_price: float | None = None  # Börsenpreis brutto
    current_gross_tax_and_levies: float | None = None  # Steuern, Umlagen & Netzentgelte brutto

    # Feste monatliche Grundgebühren (EUR/Monat)
    gross_monthly_ostrom_fee: float = 0.0  # Ostrom Grundgebühr
    gross_monthly_grid_fee: float = 0.0  # Netzentgelte Grundgebühr
    gross_monthly_base_fee: float = 0.0  # Gesamte Grundgebühr pro Monat
    daily_base_fee: float = 0.0  # Anteilige Grundgebühr pro Tag

    # Metriken & Rankings
    price_level: str = "normal"
    rank: int | None = None

    # Kosten & Verbrauch
    accrued_cost_today: float = 0.0  # Reine Verbrauchskosten heute (EUR)
    total_cost_today_with_base_fee: float = 0.0  # Verbrauchskosten + anteilige Grundgebühr heute
    energy_consumption_today: float = 0.0  # Gemessener Verbrauch heute (kWh)
    meter_reading: float | None = None

    # Verläufe & Forecast (ApexCharts / Energy Dashboard kompatibel)
    prices_today: list[dict[str, Any]] = field(default_factory=list)
    prices_tomorrow: list[dict[str, Any]] = field(default_factory=list)
    forecast: list[dict[str, Any]] = field(default_factory=list)
    contract_id: int | str | None = None


class OstromDataCoordinator(DataUpdateCoordinator[OstromData]):
    """Verwaltet Datenabruf, OAuth-Token und Berechnungen für Ostrom."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        client_id: str,
        client_secret: str,
        zip_code: str,
        entry: ConfigEntry | None = None,
    ) -> None:
        """Initialisiert den Ostrom Coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="Ostrom Comprehensive",
            update_interval=timedelta(minutes=DEFAULT_SCAN_INTERVAL_MINUTES),
        )
        self.client_id = client_id
        self.client_secret = client_secret
        self.zip_code = zip_code
        self.contract_id: int | str | None = None
        if entry is not None:
            self.config_entry = entry

        session = async_get_clientsession(hass)
        self.api = OstromApiClient(
            session=session,
            client_id=client_id,
            client_secret=client_secret,
            zip_code=zip_code,
        )

    async def _async_update_data(self) -> OstromData:
        """Holt die neuesten Daten von der Ostrom API."""
        try:
            tz_str = self.hass.config.time_zone or "UTC"
            local_tz = ZoneInfo(tz_str)
        except Exception:
            local_tz = timezone.utc

        now_utc = datetime.now(timezone.utc)
        local_now = now_utc.astimezone(local_tz)

        # Abfragezeitraum: Beginn des aktuellen Tages bis Ende des Folgetages (48h)
        start_of_day = datetime.combine(local_now.date(), time.min, tzinfo=local_tz)
        end_of_tomorrow = datetime.combine(
            local_now.date() + timedelta(days=2), time.min, tzinfo=local_tz
        )

        try:
            spot_data = await self.api.async_get_spot_prices(start_of_day, end_of_tomorrow)
        except OstromAuthError as err:
            raise UpdateFailed(f"Auth-Fehler bei Ostrom: {err}") from err
        except OstromRateLimitError as err:
            raise UpdateFailed(f"Ostrom Ratenlimit erreicht: {err}") from err
        except OstromConnectionError as err:
            raise UpdateFailed(f"Verbindungsfehler zur Ostrom API: {err}") from err
        except OstromError as err:
            raise UpdateFailed(f"Ostrom API Fehler: {err}") from err

        consumption_data = await self._async_fetch_consumption(now_utc)

        return self._process_all(spot_data, consumption_data, local_tz, now_utc)

    async def _async_fetch_consumption(
        self, now_utc: datetime
    ) -> list[dict[str, Any]]:
        """Ermittelt den Vertrag und ruft Smart-Meter-Verbrauchsdaten ab."""
        try:
            if not self.contract_id:
                contracts = await self.api.async_get_contracts()
                active_contracts = [
                    c for c in contracts if c.get("status") == "ACTIVE"
                ]
                if len(active_contracts) == 1:
                    self.contract_id = active_contracts[0]["id"]
                elif len(active_contracts) > 1:
                    _LOGGER.warning(
                        "Mehrere aktive Ostrom-Verträge gefunden; Verbrauch wird ohne "
                        "eindeutige Vertragsauswahl übersprungen"
                    )

            if self.contract_id:
                start_consumption = now_utc - timedelta(days=2)
                return await self.api.async_get_energy_consumption(
                    self.contract_id, start_consumption, now_utc
                )
        except Exception as err:
            _LOGGER.debug("Smart-Meter-Verbrauchsdaten konnten nicht geladen werden: %s", err)

        return []

    @staticmethod
    def _parse_api_date(value: str) -> datetime:
        """Parst ISO-8601-Zeitstempel inklusive UTC Z-Suffix."""
        return datetime.fromisoformat(value.replace("Z", "+00:00"))

    def _process_all(
        self,
        spot_data: list[dict[str, Any]],
        consumption_data: list[dict[str, Any]],
        local_tz: ZoneInfo | timezone,
        now_utc: datetime,
    ) -> OstromData:
        """Verarbeitet Rohdaten in strukturierte Sensorwerte inklusive voller Kostenbestandteile."""
        today = now_utc.astimezone(local_tz).date()
        tomorrow = today + timedelta(days=1)

        prices_today: list[dict[str, Any]] = []
        prices_tomorrow: list[dict[str, Any]] = []
        forecast: list[dict[str, Any]] = []
        prices_by_interval: dict[datetime, float] = {}

        current_price: float | None = None
        next_hour_price: float | None = None
        current_slot_ts: str | None = None

        current_gross_kwh_price: float | None = None
        current_gross_tax_and_levies: float | None = None

        monthly_ostrom_fee = 0.0
        monthly_grid_fee = 0.0

        for item in spot_data:
            dt = self._parse_api_date(item["date"])
            gross_kwh = float(item.get("grossKwhPrice", 0.0))
            gross_tax = float(item.get("grossKwhTaxAndLevies", 0.0))
            net_kwh = float(item.get("netKwhPrice", 0.0))
            net_tax = float(item.get("netKwhTaxAndLevies", 0.0))

            # Gesamt-Arbeitspreis (EUR/kWh)
            gross_total_kwh = (gross_kwh + gross_tax) / 100.0

            if "grossMonthlyOstromBaseFee" in item:
                monthly_ostrom_fee = float(item["grossMonthlyOstromBaseFee"])
            if "grossMonthlyGridFees" in item:
                monthly_grid_fee = float(item["grossMonthlyGridFees"])

            prices_by_interval[dt] = gross_total_kwh
            local_dt = dt.astimezone(local_tz)
            end_dt = local_dt + timedelta(hours=1)

            entry_dict = {
                "start": local_dt.isoformat(),
                "end": end_dt.isoformat(),
                "time": local_dt.strftime("%H:%M"),
                "timestamp": local_dt.isoformat(),
                "value": round(gross_total_kwh, 5),  # EUR/kWh (ApexCharts Standard)
                "price": round(gross_total_kwh, 5),  # EUR/kWh
                "price_ct": round(gross_kwh + gross_tax, 2),  # ct/kWh
                "boersenpreis_brutto_ct": round(gross_kwh, 2),
                "steuern_abgaben_netzentgelte_ct": round(gross_tax, 2),
                "net_price": round(net_kwh / 100.0, 5),
                "net_tax_and_levies": round(net_tax / 100.0, 5),
            }

            forecast.append(entry_dict)

            if local_dt.date() == today:
                prices_today.append(entry_dict)
            elif local_dt.date() == tomorrow:
                prices_tomorrow.append(entry_dict)

            # Prüfe aktuellen Stundenslot
            if dt <= now_utc < (dt + timedelta(hours=1)):
                current_price = round(gross_total_kwh, 5)
                current_slot_ts = local_dt.isoformat()
                current_gross_kwh_price = round(gross_kwh, 2)
                current_gross_tax_and_levies = round(gross_tax, 2)

            # Prüfe nächste Stunde
            if (dt - timedelta(hours=1)) <= now_utc < dt:
                next_hour_price = round(gross_total_kwh, 5)

        # Statistiken heute
        vals_today = [p["price"] for p in prices_today]
        avg_today = round(sum(vals_today) / len(vals_today), 4) if vals_today else 0.0
        min_today = min(vals_today) if vals_today else 0.0
        max_today = max(vals_today) if vals_today else 0.0

        min_item_today = min(prices_today, key=lambda x: x["price"]) if prices_today else None
        max_item_today = max(prices_today, key=lambda x: x["price"]) if prices_today else None
        min_price_time_today = min_item_today["time"] if min_item_today else None
        max_price_time_today = max_item_today["time"] if max_item_today else None

        # Statistiken morgen
        vals_tomorrow = [p["price"] for p in prices_tomorrow]
        avg_tomorrow = round(sum(vals_tomorrow) / len(vals_tomorrow), 4) if vals_tomorrow else None
        min_tomorrow = min(vals_tomorrow) if vals_tomorrow else None
        max_tomorrow = max(vals_tomorrow) if vals_tomorrow else None

        min_item_tomorrow = min(prices_tomorrow, key=lambda x: x["price"]) if prices_tomorrow else None
        max_item_tomorrow = max(prices_tomorrow, key=lambda x: x["price"]) if prices_tomorrow else None
        min_price_time_tomorrow = min_item_tomorrow["time"] if min_item_tomorrow else None
        max_price_time_tomorrow = max_item_tomorrow["time"] if max_item_tomorrow else None

        # Preisstufe & Rang
        price_level = "normal"
        rank = None
        if avg_today > 0 and current_price is not None:
            ratio = current_price / avg_today
            if ratio <= 0.80:
                price_level = "sehr_guenstig"
            elif ratio <= 0.95:
                price_level = "guenstig"
            elif ratio <= 1.05:
                price_level = "normal"
            elif ratio <= 1.20:
                price_level = "teuer"
            else:
                price_level = "sehr_teuer"

            sorted_by_price = sorted(prices_today, key=lambda p: p["price"])
            for idx, item in enumerate(sorted_by_price):
                if item["timestamp"] == current_slot_ts:
                    rank = idx + 1
                    break

        monthly_base_total = round(monthly_ostrom_fee + monthly_grid_fee, 2)
        daily_base_fee = round((monthly_base_total * 12) / 365.0, 3)

        accrued_cost_today = 0.0
        energy_consumption_today = 0.0
        for item in consumption_data:
            consumption_dt = self._parse_api_date(item["date"])
            if consumption_dt.astimezone(local_tz).date() == today:
                kwh = float(item.get("kWh", 0.0))
                energy_consumption_today += kwh
                unit_price = prices_by_interval.get(consumption_dt)
                if unit_price is not None:
                    accrued_cost_today += kwh * unit_price

        accrued_cost_today = round(accrued_cost_today, 2)
        total_cost_today_with_base_fee = round(accrued_cost_today + daily_base_fee, 2)

        return OstromData(
            current_price=current_price,
            next_hour_price=next_hour_price,
            avg_today=avg_today,
            min_today=min_today,
            max_today=max_today,
            min_price_time_today=min_price_time_today,
            max_price_time_today=max_price_time_today,
            avg_tomorrow=avg_tomorrow,
            min_tomorrow=min_tomorrow,
            max_tomorrow=max_tomorrow,
            min_price_time_tomorrow=min_price_time_tomorrow,
            max_price_time_tomorrow=max_price_time_tomorrow,
            current_gross_kwh_price=current_gross_kwh_price,
            current_gross_tax_and_levies=current_gross_tax_and_levies,
            gross_monthly_ostrom_fee=monthly_ostrom_fee,
            gross_monthly_grid_fee=monthly_grid_fee,
            gross_monthly_base_fee=monthly_base_total,
            daily_base_fee=daily_base_fee,
            price_level=price_level,
            rank=rank,
            meter_reading=None,
            accrued_cost_today=accrued_cost_today,
            total_cost_today_with_base_fee=total_cost_today_with_base_fee,
            energy_consumption_today=round(energy_consumption_today, 3),
            prices_today=prices_today,
            prices_tomorrow=prices_tomorrow,
            forecast=forecast,
            contract_id=self.contract_id,
        )

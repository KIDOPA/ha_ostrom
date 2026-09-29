"""DataUpdateCoordinator für Ostrom mit Preisen, Verträgen und Verbrauch."""
from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
import logging
import math
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
    daily_base_fee: float = 0.0  # Anteilige Grundgebühr heute
    daily_base_fee_yesterday: float = 0.0  # Anteilige Grundgebühr gestern
    daily_base_fee_48h: float = 0.0  # Anteilige Grundgebühr vor 48h
    hourly_base_fee_today: float = 0.0  # Anteilige Grundgebühr pro Stunde heute
    hourly_base_fee_yesterday: float = 0.0  # Anteilige Grundgebühr pro Stunde gestern
    hourly_base_fee_48h: float = 0.0  # Anteilige Grundgebühr pro Stunde vor 48h

    # Metriken & Rankings
    price_level: str = "normal"
    rank: int | None = None

    # Kosten & Verbrauch heute
    accrued_cost_today: float = 0.0  # Reine Verbrauchskosten heute (EUR)
    total_cost_today_with_base_fee: float = 0.0  # Verbrauchskosten + anteilige Grundgebühr heute
    energy_consumption_today: float = 0.0  # Gemessener Verbrauch heute (kWh)
    meter_reading: float | None = None

    # Kosten & Verbrauch gestern (Vortag / T-1)
    accrued_cost_yesterday: float | None = None
    total_cost_yesterday_with_base_fee: float | None = None
    market_cost_yesterday: float | None = None
    tax_cost_yesterday: float | None = None
    energy_consumption_yesterday: float | None = None
    yesterday_date: str | None = None
    hourly_breakdown_yesterday: list[dict[str, Any]] = field(default_factory=list)

    # Kosten & Verbrauch vor 48h (vor 2 Tagen / T-2)
    accrued_cost_48h: float | None = None
    total_cost_48h_with_base_fee: float | None = None
    market_cost_48h: float | None = None
    tax_cost_48h: float | None = None
    energy_consumption_48h: float | None = None
    date_48h: str | None = None
    hourly_breakdown_48h: list[dict[str, Any]] = field(default_factory=list)

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
        start_of_past = datetime.combine(
            local_now.date() - timedelta(days=2), time.min, tzinfo=timezone.utc
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

        # Historische Spotpreise für vor 48h und gestern abrufen (für Kostenberechnung)
        all_spot_data = list(spot_data)
        try:
            past_spot_data = await self.api.async_get_spot_prices(start_of_past, start_of_day)
            all_spot_data = past_spot_data + spot_data
        except Exception as err:
            _LOGGER.debug("Historische Spotpreise konnten nicht geladen werden: %s", err)

        consumption_data = await self._async_fetch_consumption(local_now, local_tz)

        return self._process_all(all_spot_data, consumption_data, local_tz, now_utc)

    async def _async_fetch_consumption(
        self, local_now: datetime, local_tz: ZoneInfo | timezone
    ) -> list[dict[str, Any]]:
        """Ermittelt den Vertrag und ruft Smart-Meter-Verbrauchsdaten ab."""
        try:
            if not self.contract_id:
                contracts = await self.api.async_get_contracts()
                if contracts:
                    active = [
                        c for c in contracts
                        if str(c.get("status", "")).upper() in ("ACTIVE", "IN_DELIVERY", "IN_SUPPLY", "CONFIRMED")
                    ]
                    if active:
                        self.contract_id = active[0]["id"]
                    else:
                        self.contract_id = contracts[0]["id"]
                    _LOGGER.info("Ostrom Vertrag für Verbrauch erkannt: ID %s", self.contract_id)

            if self.contract_id:
                start_consumption = datetime.combine(
                    local_now.date() - timedelta(days=2), time.min, tzinfo=timezone.utc
                )
                end_consumption = datetime.combine(
                    local_now.date() + timedelta(days=1), time.min, tzinfo=timezone.utc
                )
                return await self.api.async_get_energy_consumption(
                    self.contract_id, start_consumption, end_consumption
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
        market_by_interval: dict[datetime, float] = {}
        tax_by_interval: dict[datetime, float] = {}

        prices_by_hour_key: dict[str, float] = {}
        market_by_hour_key: dict[str, float] = {}
        tax_by_hour_key: dict[str, float] = {}

        current_price: float | None = None
        next_hour_price: float | None = None
        current_slot_ts: str | None = None

        current_gross_kwh_price: float | None = None
        current_gross_tax_and_levies: float | None = None

        monthly_ostrom_fee = 0.0
        monthly_grid_fee = 0.0

        for item in spot_data:
            dt = self._parse_api_date(item["date"]).replace(minute=0, second=0, microsecond=0)
            gross_kwh = float(item.get("grossKwhPrice", 0.0))
            gross_tax = float(item.get("grossKwhTaxAndLevies", 0.0))
            net_kwh = float(item.get("netKwhPrice", 0.0))
            net_tax = float(item.get("netKwhTaxAndLevies", 0.0))

            # Gesamt-Arbeitspreis (EUR/kWh)
            gross_total_kwh = (gross_kwh + gross_tax) / 100.0
            gross_market_kwh = gross_kwh / 100.0
            gross_tax_kwh = gross_tax / 100.0

            if "grossMonthlyOstromBaseFee" in item:
                monthly_ostrom_fee = float(item["grossMonthlyOstromBaseFee"])
            if "grossMonthlyGridFees" in item:
                monthly_grid_fee = float(item["grossMonthlyGridFees"])

            prices_by_interval[dt] = gross_total_kwh
            market_by_interval[dt] = gross_market_kwh
            tax_by_interval[dt] = gross_tax_kwh

            raw_ts = str(item.get("date", ""))
            if len(raw_ts) >= 13:
                h_key = raw_ts[:13]
                prices_by_hour_key[h_key] = gross_total_kwh
                market_by_hour_key[h_key] = gross_market_kwh
                tax_by_hour_key[h_key] = gross_tax_kwh

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

            if local_dt.date() >= today:
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

        yesterday = today - timedelta(days=1)
        two_days_ago = today - timedelta(days=2)

        def _calculate_daily_base_fee(target_date: date) -> float:
            if monthly_base_total <= 0:
                return 0.0
            days_in_month = calendar.monthrange(target_date.year, target_date.month)[1]
            return round(math.ceil(monthly_base_total / days_in_month * 100) / 100, 2)

        def _calculate_hourly_base_fee(target_date: date) -> float:
            if monthly_base_total <= 0:
                return 0.0
            days_in_month = calendar.monthrange(target_date.year, target_date.month)[1]
            return round(monthly_base_total / (days_in_month * 24), 5)

        daily_base_fee_today = _calculate_daily_base_fee(today)
        daily_base_fee_yesterday = _calculate_daily_base_fee(yesterday)
        daily_base_fee_48h = _calculate_daily_base_fee(two_days_ago)

        hourly_base_fee_today = _calculate_hourly_base_fee(today)
        hourly_base_fee_yesterday = _calculate_hourly_base_fee(yesterday)
        hourly_base_fee_48h = _calculate_hourly_base_fee(two_days_ago)

        today_str = str(today)
        yesterday_str = str(yesterday)
        two_days_ago_str = str(two_days_ago)

        sorted_consumption = sorted(consumption_data, key=lambda x: str(x.get("date", "")))

        hourly_breakdown_today: list[dict[str, Any]] = []
        hourly_breakdown_yesterday: list[dict[str, Any]] = []
        hourly_breakdown_48h: list[dict[str, Any]] = []

        has_today = False
        kwh_today = 0.0
        cost_today = 0.0
        market_cost_today = 0.0
        tax_cost_today = 0.0

        has_yesterday = False
        kwh_yesterday = 0.0
        cost_yesterday = 0.0
        market_cost_yesterday = 0.0
        tax_cost_yesterday = 0.0

        has_48h = False
        kwh_48h = 0.0
        cost_48h = 0.0
        market_cost_48h = 0.0
        tax_cost_48h = 0.0

        for item in sorted_consumption:
            raw_date = str(item.get("date", ""))
            date_day = raw_date[:10]
            hour_key = raw_date[:13] if len(raw_date) >= 13 else ""

            try:
                consumption_dt = self._parse_api_date(raw_date).replace(
                    minute=0, second=0, microsecond=0
                )
                hour_num = consumption_dt.hour
            except Exception:
                consumption_dt = None
                hour_num = (
                    int(raw_date[11:13])
                    if len(raw_date) >= 13 and raw_date[11:13].isdigit()
                    else 0
                )

            kwh = float(item.get("kWh", item.get("kwh", item.get("consumptionKwh", 0.0))))

            unit_price = prices_by_hour_key.get(hour_key)
            market_price = market_by_hour_key.get(hour_key)
            tax_price = tax_by_hour_key.get(hour_key)

            if unit_price is None and consumption_dt is not None:
                unit_price = prices_by_interval.get(consumption_dt)
                market_price = market_by_interval.get(consumption_dt)
                tax_price = tax_by_interval.get(consumption_dt)

            cost_slot = round(kwh * unit_price, 4) if unit_price is not None else 0.0
            market_slot = round(kwh * market_price, 4) if market_price is not None else 0.0
            tax_slot = round(kwh * tax_price, 4) if tax_price is not None else 0.0

            if date_day == today_str:
                h_fee = hourly_base_fee_today
            elif date_day == yesterday_str:
                h_fee = hourly_base_fee_yesterday
            elif date_day == two_days_ago_str:
                h_fee = hourly_base_fee_48h
            else:
                h_fee = 0.0

            slot_entry = {
                "uhrzeit": f"{hour_num:02d}:00 - {(hour_num + 1) % 24:02d}:00",
                "verbrauch_kwh": round(kwh, 4),
                "arbeitspreis_eur_kwh": round(unit_price, 5) if unit_price is not None else None,
                "marktpreis_eur_kwh": round(market_price, 5) if market_price is not None else None,
                "abgaben_eur_kwh": round(tax_price, 5) if tax_price is not None else None,
                "kosten_reiner_verbrauch_eur": cost_slot,
                "anteilige_grundgebuehr_stunde_eur": h_fee,
                "kosten_gesamt_inkl_grundgebuehr_eur": round(cost_slot + h_fee, 4),
                "kosten_eur": cost_slot,
            }

            if date_day == today_str:
                has_today = True
                kwh_today += kwh
                cost_today += cost_slot
                market_cost_today += market_slot
                tax_cost_today += tax_slot
                hourly_breakdown_today.append(slot_entry)
            elif date_day == yesterday_str:
                has_yesterday = True
                kwh_yesterday += kwh
                cost_yesterday += cost_slot
                market_cost_yesterday += market_slot
                tax_cost_yesterday += tax_slot
                hourly_breakdown_yesterday.append(slot_entry)
            elif date_day == two_days_ago_str:
                has_48h = True
                kwh_48h += kwh
                cost_48h += cost_slot
                market_cost_48h += market_slot
                tax_cost_48h += tax_slot
                hourly_breakdown_48h.append(slot_entry)

        # Kosten heute
        accrued_cost_today = round(cost_today, 2)
        total_cost_today_with_base_fee = round(accrued_cost_today + daily_base_fee_today, 2)
        energy_consumption_today = round(kwh_today, 3)

        # Kosten & Verbrauch gestern (Vortag / T-1)
        accrued_cost_yesterday = round(cost_yesterday, 2) if has_yesterday else None
        total_cost_yesterday_with_base_fee = (
            round(cost_yesterday + daily_base_fee_yesterday, 2) if has_yesterday else None
        )
        market_cost_yesterday_val = (
            round(market_cost_yesterday, 2) if has_yesterday else None
        )
        tax_cost_yesterday_val = (
            round(tax_cost_yesterday, 2) if has_yesterday else None
        )
        energy_consumption_yesterday = (
            round(kwh_yesterday, 3) if has_yesterday else None
        )

        # Kosten & Verbrauch vor 48h (vor 2 Tagen / T-2)
        accrued_cost_48h = round(cost_48h, 2) if has_48h else None
        total_cost_48h_with_base_fee = (
            round(cost_48h + daily_base_fee_48h, 2) if has_48h else None
        )
        market_cost_48h_val = (
            round(market_cost_48h, 2) if has_48h else None
        )
        tax_cost_48h_val = (
            round(tax_cost_48h, 2) if has_48h else None
        )
        energy_consumption_48h = (
            round(kwh_48h, 3) if has_48h else None
        )

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
            daily_base_fee=daily_base_fee_today,
            daily_base_fee_yesterday=daily_base_fee_yesterday,
            daily_base_fee_48h=daily_base_fee_48h,
            hourly_base_fee_today=hourly_base_fee_today,
            hourly_base_fee_yesterday=hourly_base_fee_yesterday,
            hourly_base_fee_48h=hourly_base_fee_48h,
            price_level=price_level,
            rank=rank,
            meter_reading=None,
            accrued_cost_today=accrued_cost_today,
            total_cost_today_with_base_fee=total_cost_today_with_base_fee,
            energy_consumption_today=energy_consumption_today,
            accrued_cost_yesterday=accrued_cost_yesterday,
            total_cost_yesterday_with_base_fee=total_cost_yesterday_with_base_fee,
            market_cost_yesterday=market_cost_yesterday_val,
            tax_cost_yesterday=tax_cost_yesterday_val,
            energy_consumption_yesterday=energy_consumption_yesterday,
            yesterday_date=str(yesterday),
            hourly_breakdown_yesterday=hourly_breakdown_yesterday,
            accrued_cost_48h=accrued_cost_48h,
            total_cost_48h_with_base_fee=total_cost_48h_with_base_fee,
            market_cost_48h=market_cost_48h_val,
            tax_cost_48h=tax_cost_48h_val,
            energy_consumption_48h=energy_consumption_48h,
            date_48h=str(two_days_ago),
            hourly_breakdown_48h=hourly_breakdown_48h,
            prices_today=prices_today,
            prices_tomorrow=prices_tomorrow,
            forecast=forecast,
            contract_id=self.contract_id,
        )

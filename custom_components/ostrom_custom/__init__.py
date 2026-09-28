"""Initialisierung der Ostrom Integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_change

from .const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_ZIP_CODE,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import OstromDataCoordinator

_LOGGER = logging.getLogger(__name__)

type OstromConfigEntry = ConfigEntry[OstromDataCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: OstromConfigEntry) -> bool:
    """Richtet Ostrom aus einem ConfigEntry ein."""
    hass.data.setdefault(DOMAIN, {})

    coordinator = OstromDataCoordinator(
        hass=hass,
        client_id=entry.data[CONF_CLIENT_ID],
        client_secret=entry.data[CONF_CLIENT_SECRET],
        zip_code=entry.data[CONF_ZIP_CODE],
        entry=entry,
    )

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    hass.data[DOMAIN][entry.entry_id] = coordinator

    async def _async_hourly_listener(*_args: object) -> None:
        coordinator.async_update_listeners()

    entry.async_on_unload(
        async_track_time_change(hass, _async_hourly_listener, minute=0, second=1)
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: OstromConfigEntry) -> bool:
    """Entlädt einen ConfigEntry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unload_ok

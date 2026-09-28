"""Config flow für die Ostrom Integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    OstromApiClient,
    OstromAuthError,
    OstromConnectionError,
    OstromRateLimitError,
)
from .const import CONF_CLIENT_ID, CONF_CLIENT_SECRET, CONF_ZIP_CODE, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CLIENT_ID): str,
        vol.Required(CONF_CLIENT_SECRET): str,
        vol.Required(CONF_ZIP_CODE): str,
    }
)


class OstromConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Verwaltet den Konfigurations-Ablauf für Ostrom."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Erster Schritt bei manueller Einrichtung über die UI."""
        errors: dict[str, str] = {}

        if user_input is not None:
            client_id = user_input[CONF_CLIENT_ID].strip()
            client_secret = user_input[CONF_CLIENT_SECRET].strip()
            zip_code = user_input[CONF_ZIP_CODE].strip()

            user_input[CONF_CLIENT_ID] = client_id
            user_input[CONF_CLIENT_SECRET] = client_secret
            user_input[CONF_ZIP_CODE] = zip_code

            # Verhindern, dass derselbe Account mehrfach angelegt wird
            await self.async_set_unique_id(client_id)
            self._abort_if_unique_id_configured()

            session = async_get_clientsession(self.hass)
            client = OstromApiClient(
                session=session,
                client_id=client_id,
                client_secret=client_secret,
                zip_code=zip_code,
            )

            try:
                await client.async_validate_credentials()
            except OstromAuthError:
                errors["base"] = "invalid_auth"
            except OstromRateLimitError:
                errors["base"] = "rate_limited"
            except OstromConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unerwarteter Fehler bei der Ostrom-Konfiguration")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(
                    title=f"Ostrom ({zip_code})",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Fehler: Verbindung zur Ostrom-API nicht möglich."""


class InvalidAuth(HomeAssistantError):
    """Fehler: Ungültige Zugangsdaten."""

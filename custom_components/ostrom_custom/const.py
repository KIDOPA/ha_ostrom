"""Konstanten für die Ostrom Integration."""
from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "ostrom_custom"

# Konfigurations-Keys
CONF_CLIENT_ID = "client_id"
CONF_CLIENT_SECRET = "client_secret"
CONF_ZIP_CODE = "zip_code"

# API Endpunkte
AUTH_URL = "https://auth.production.ostrom-api.io/oauth2/token"
BASE_URL = "https://production.ostrom-api.io"

# Unterstützte Plattformen
PLATFORMS: list[Platform] = [
    Platform.SENSOR,
]

# Standard Update-Intervall (Minuten)
DEFAULT_SCAN_INTERVAL_MINUTES = 30

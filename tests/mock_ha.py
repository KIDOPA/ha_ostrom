"""Mock environment for Home Assistant when running standalone tests without HA installed."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import sys
import types
from typing import Any
from unittest.mock import MagicMock


def setup_mock_ha() -> None:
    if "homeassistant" in sys.modules:
        return

    # aiohttp mock
    if "aiohttp" not in sys.modules:
        aiohttp = types.ModuleType("aiohttp")

        class ClientError(Exception):
            pass

        class ClientSession:
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                pass

        class BasicAuth:
            def __init__(self, login: str, password: str, encoding: str = "latin1") -> None:
                self.login = login
                self.password = password
                self.encoding = encoding

            def encode(self) -> str:
                import base64
                creds = f"{self.login}:{self.password}".encode(self.encoding)
                return f"Basic {base64.b64encode(creds).decode('ascii')}"

        class ClientTimeout:
            def __init__(self, total: float = 15) -> None:
                self.total = total

        aiohttp.ClientError = ClientError
        aiohttp.ClientSession = ClientSession
        aiohttp.BasicAuth = BasicAuth
        aiohttp.ClientTimeout = ClientTimeout
        sys.modules["aiohttp"] = aiohttp

    # voluptuous mock
    if "voluptuous" not in sys.modules:
        vol = types.ModuleType("voluptuous")

        class Schema:
            def __init__(self, schema: Any) -> None:
                self.schema = schema

            def __call__(self, data: Any) -> Any:
                return data

        def Required(key: Any) -> Any:
            return key

        def Optional(key: Any) -> Any:
            return key

        vol.Schema = Schema
        vol.Required = Required
        vol.Optional = Optional
        sys.modules["voluptuous"] = vol

    # homeassistant mock modules
    ha = types.ModuleType("homeassistant")
    sys.modules["homeassistant"] = ha

    ha_const = types.ModuleType("homeassistant.const")

    class Platform(str, Enum):
        SENSOR = "sensor"

    class UnitOfEnergy(str, Enum):
        KILO_WATT_HOUR = "kWh"

    ha_const.Platform = Platform
    ha_const.UnitOfEnergy = UnitOfEnergy
    sys.modules["homeassistant.const"] = ha_const

    ha_exceptions = types.ModuleType("homeassistant.exceptions")

    class HomeAssistantError(Exception):
        pass

    ha_exceptions.HomeAssistantError = HomeAssistantError
    sys.modules["homeassistant.exceptions"] = ha_exceptions

    ha_core = types.ModuleType("homeassistant.core")

    class Config:
        def __init__(self) -> None:
            self.time_zone = "UTC"

    class HomeAssistant:
        def __init__(self) -> None:
            self.data: dict[str, Any] = {}
            self.config = Config()
            self.config_entries = MagicMock()

    ha_core.HomeAssistant = HomeAssistant
    sys.modules["homeassistant.core"] = ha_core

    ha_config_entries = types.ModuleType("homeassistant.config_entries")

    class ConfigEntry:
        __class_getitem__ = classmethod(lambda cls, *args: cls)

        def __init__(
            self,
            version: int = 1,
            domain: str = "ostrom_custom",
            title: str = "Ostrom",
            data: dict[str, Any] | None = None,
            entry_id: str = "test_entry_id",
            unique_id: str | None = None,
        ) -> None:
            self.version = version
            self.domain = domain
            self.title = title
            self.data = data or {}
            self.entry_id = entry_id
            self.unique_id = unique_id
            self.runtime_data = None
            self._on_unload = []

        def async_on_unload(self, callback: Any) -> None:
            self._on_unload.append(callback)

    class ConfigFlow:
        VERSION = 1

        def __init_subclass__(cls, domain: str | None = None, **kwargs: Any) -> None:
            super().__init_subclass__(**kwargs)
            cls.domain = domain

        def __init__(self) -> None:
            self.hass = MagicMock()
            self.unique_id = None
            self._abort_entries = []

        async def async_set_unique_id(self, unique_id: str) -> None:
            self.unique_id = unique_id

        def _abort_if_unique_id_configured(self) -> None:
            if self.unique_id in self._abort_entries:
                raise AbortFlow("already_configured")

        def async_show_form(
            self, step_id: str, data_schema: Any = None, errors: dict[str, str] | None = None
        ) -> dict[str, Any]:
            return {
                "type": "form",
                "step_id": step_id,
                "data_schema": data_schema,
                "errors": errors or {},
            }

        def async_create_entry(self, title: str, data: dict[str, Any]) -> dict[str, Any]:
            return {
                "type": "create_entry",
                "title": title,
                "data": data,
            }

    class AbortFlow(HomeAssistantError):
        pass

    ha_config_entries.ConfigEntry = ConfigEntry
    ha_config_entries.ConfigFlow = ConfigFlow
    ha_config_entries.AbortFlow = AbortFlow
    sys.modules["homeassistant.config_entries"] = ha_config_entries

    ha_data_entry_flow = types.ModuleType("homeassistant.data_entry_flow")
    FlowResult = dict[str, Any]
    ha_data_entry_flow.FlowResult = FlowResult
    sys.modules["homeassistant.data_entry_flow"] = ha_data_entry_flow

    ha_helpers = types.ModuleType("homeassistant.helpers")
    sys.modules["homeassistant.helpers"] = ha_helpers

    ha_helpers_aiohttp = types.ModuleType("homeassistant.helpers.aiohttp_client")

    def async_get_clientsession(hass: Any) -> Any:
        return getattr(hass, "session", MagicMock())

    ha_helpers_aiohttp.async_get_clientsession = async_get_clientsession
    sys.modules["homeassistant.helpers.aiohttp_client"] = ha_helpers_aiohttp

    ha_helpers_coord = types.ModuleType("homeassistant.helpers.update_coordinator")

    class UpdateFailed(HomeAssistantError):
        pass

    class DataUpdateCoordinator:
        __class_getitem__ = classmethod(lambda cls, *args: cls)

        def __init__(self, hass: Any, logger: Any, name: str, update_interval: Any) -> None:
            self.hass = hass
            self.logger = logger
            self.name = name
            self.update_interval = update_interval
            self.data = None
            self._listeners = []

        def async_update_listeners(self) -> None:
            for listener in self._listeners:
                listener()

        def async_add_listener(self, update_callback: Any) -> Any:
            self._listeners.append(update_callback)
            return lambda: self._listeners.remove(update_callback)

        async def async_config_entry_first_refresh(self) -> None:
            self.data = await self._async_update_data()

        async def _async_update_data(self) -> Any:
            raise NotImplementedError

    class CoordinatorEntity:
        __class_getitem__ = classmethod(lambda cls, *args: cls)

        def __init__(self, coordinator: Any) -> None:
            self.coordinator = coordinator

    ha_helpers_coord.UpdateFailed = UpdateFailed
    ha_helpers_coord.DataUpdateCoordinator = DataUpdateCoordinator
    ha_helpers_coord.CoordinatorEntity = CoordinatorEntity
    sys.modules["homeassistant.helpers.update_coordinator"] = ha_helpers_coord

    ha_helpers_dev = types.ModuleType("homeassistant.helpers.device_registry")

    class DeviceEntryType(str, Enum):
        SERVICE = "service"

    @dataclass
    class DeviceInfo:
        identifiers: set[tuple[str, str]]
        name: str
        manufacturer: str
        model: str
        entry_type: DeviceEntryType

    ha_helpers_dev.DeviceEntryType = DeviceEntryType
    ha_helpers_dev.DeviceInfo = DeviceInfo
    sys.modules["homeassistant.helpers.device_registry"] = ha_helpers_dev

    ha_helpers_ep = types.ModuleType("homeassistant.helpers.entity_platform")
    AddEntitiesCallback = Any
    ha_helpers_ep.AddEntitiesCallback = AddEntitiesCallback
    sys.modules["homeassistant.helpers.entity_platform"] = ha_helpers_ep

    ha_helpers_event = types.ModuleType("homeassistant.helpers.event")

    def async_track_time_change(hass: Any, action: Any, **kwargs: Any) -> Any:
        return MagicMock()

    ha_helpers_event.async_track_time_change = async_track_time_change
    sys.modules["homeassistant.helpers.event"] = ha_helpers_event

    ha_components = types.ModuleType("homeassistant.components")
    sys.modules["homeassistant.components"] = ha_components

    ha_components_sensor = types.ModuleType("homeassistant.components.sensor")

    class SensorEntity:
        _attr_has_entity_name: bool = False
        _attr_name: str | None = None
        _attr_unique_id: str | None = None
        _attr_device_class: Any = None
        _attr_state_class: Any = None
        _attr_native_unit_of_measurement: str | None = None
        _attr_icon: str | None = None

        @property
        def unique_id(self) -> str | None:
            return self._attr_unique_id

        @property
        def name(self) -> str | None:
            return self._attr_name

        @property
        def device_class(self) -> Any:
            return self._attr_device_class

        @property
        def state_class(self) -> Any:
            return self._attr_state_class

        @property
        def native_unit_of_measurement(self) -> str | None:
            return self._attr_native_unit_of_measurement

        @property
        def native_value(self) -> Any:
            return None

        @property
        def extra_state_attributes(self) -> dict[str, Any]:
            return {}

    class SensorDeviceClass(str, Enum):
        MONETARY = "monetary"
        ENERGY = "energy"

    class SensorStateClass(str, Enum):
        TOTAL = "total"
        TOTAL_INCREASING = "total_increasing"

    ha_components_sensor.SensorEntity = SensorEntity
    ha_components_sensor.SensorDeviceClass = SensorDeviceClass
    ha_components_sensor.SensorStateClass = SensorStateClass
    sys.modules["homeassistant.components.sensor"] = ha_components_sensor


setup_mock_ha()

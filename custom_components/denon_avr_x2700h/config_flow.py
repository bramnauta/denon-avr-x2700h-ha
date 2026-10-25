"""Config flow for the Denon AVR-X2700H integration."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import format_mac

from .client import async_probe
from .const import (
    CONF_MAX_VOLUME,
    CONF_VOLUME_STEP,
    CONF_ZONE2,
    DEFAULT_MAX_VOLUME,
    DEFAULT_NAME,
    DEFAULT_VOLUME_STEP,
    DEFAULT_ZONE2,
    DOMAIN,
    MANUFACTURER,
)
from .webapi import async_get_device_info

try:
    from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo
except ImportError:  # Home Assistant < 2025.1
    from homeassistant.components.ssdp import SsdpServiceInfo  # type: ignore[no-redef]


class DenonConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self._host: str | None = None
        self._name: str | None = None

    async def _async_identify(self, host: str) -> tuple[str, str]:
        """Return (unique_id, name) for a host."""
        info = await async_get_device_info(async_get_clientsession(self.hass), host)
        unique_id = format_mac(info.mac) if info.mac else host
        return unique_id, f"{MANUFACTURER} {info.model}"

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual setup."""
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            if not await async_probe(host):
                errors["base"] = "cannot_connect"
            else:
                unique_id, name = await self._async_identify(host)
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured(updates={CONF_HOST: host})
                return self.async_create_entry(
                    title=user_input.get(CONF_NAME) or name,
                    data={CONF_HOST: host},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=self._host or ""): str,
                    vol.Optional(CONF_NAME): str,
                }
            ),
            errors=errors,
        )

    async def async_step_ssdp(
        self, discovery_info: SsdpServiceInfo
    ) -> ConfigFlowResult:
        """Handle SSDP discovery."""
        host = urlparse(discovery_info.ssdp_location or "").hostname
        if not host:
            return self.async_abort(reason="cannot_connect")
        unique_id, name = await self._async_identify(host)
        await self.async_set_unique_id(unique_id)
        self._abort_if_unique_id_configured(updates={CONF_HOST: host})
        self._host = host
        self._name = name
        self.context["title_placeholders"] = {"name": name}
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm a discovered receiver."""
        assert self._host is not None
        errors: dict[str, str] = {}
        if user_input is not None:
            if await async_probe(self._host):
                return self.async_create_entry(
                    title=self._name or DEFAULT_NAME, data={CONF_HOST: self._host}
                )
            errors["base"] = "cannot_connect"
        return self.async_show_form(
            step_id="confirm",
            description_placeholders={"name": self._name or "", "host": self._host},
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Change the host of an existing entry."""
        entry = self._get_reconfigure_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            if await async_probe(host):
                return self.async_update_reload_and_abort(
                    entry, data_updates={CONF_HOST: host}
                )
            errors["base"] = "cannot_connect"
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {vol.Required(CONF_HOST, default=entry.data[CONF_HOST]): str}
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow."""
        return DenonOptionsFlow()


class DenonOptionsFlow(OptionsFlow):
    """Options: zone 2, volume scaling and step."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        options = self.config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_ZONE2, default=options.get(CONF_ZONE2, DEFAULT_ZONE2)
                    ): bool,
                    vol.Required(
                        CONF_MAX_VOLUME,
                        default=options.get(CONF_MAX_VOLUME, DEFAULT_MAX_VOLUME),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=-40,
                            max=18,
                            step=0.5,
                            unit_of_measurement="dB",
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Required(
                        CONF_VOLUME_STEP,
                        default=options.get(CONF_VOLUME_STEP, DEFAULT_VOLUME_STEP),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0.5,
                            max=5,
                            step=0.5,
                            unit_of_measurement="dB",
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                }
            ),
        )

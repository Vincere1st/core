"""Support for Freebox covers."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_CLOSED, STATE_OPEN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_platform
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, FreeboxHomeCategory
from .entity import FreeboxHomeEntity
from .router import FreeboxRouter

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the covers."""
    router: FreeboxRouter = hass.data[DOMAIN][entry.unique_id]
    tracked: set[str] = set()

    @callback
    def update_callback() -> None:
        add_entities(hass, router, async_add_entities, tracked)

    router.listeners.append(
        async_dispatcher_connect(hass, router.signal_home_device_new, update_callback)
    )
    update_callback()

    entity_platform.async_get_current_platform()


@callback
def add_entities(
    hass: HomeAssistant,
    router: FreeboxRouter,
    async_add_entities: AddEntitiesCallback,
    tracked: set[str],
) -> None:
    """Add new covers from the router."""
    new_tracked: list[FreeboxCover] = []

    for nodeid, node in router.home_devices.items():
        if (node["category"] != FreeboxHomeCategory.SHUTTER) or (nodeid in tracked):
            continue
        new_tracked.append(FreeboxCover(hass, router, node))
        tracked.add(nodeid)

    if new_tracked:
        async_add_entities(new_tracked, True)


class FreeboxCover(FreeboxHomeEntity, CoverEntity):
    """Representation of a Freebox shutter."""

    def __init__(
        self, hass: HomeAssistant, router: FreeboxRouter, node: dict[str, Any]
    ) -> None:
        """Initialize the cover."""
        super().__init__(hass, router, node)
        self._command_up = self.get_command_id(node["show_endpoints"], "slot", "up")
        self._command_stop = self.get_command_id(node["show_endpoints"], "slot", "stop")
        self._command_down = self.get_command_id(node["show_endpoints"], "slot", "down")
        self._command_state = self.get_command_id(
            node["show_endpoints"], "signal", "state"
        )
        self._state = self.get_node_value(node["show_endpoints"], "signal", "state")
        if node["category"] == FreeboxHomeCategory.SHUTTER:
            self._attr_device_class = CoverDeviceClass.SHUTTER

        CoverEntity.__init__(self)

    @property
    def supported_features(self) -> CoverEntityFeature:
        """Flag supported features."""
        return (
            CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
        )

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed or not."""
        if self._state == STATE_OPEN:
            return False
        if self._state == STATE_CLOSED:
            return True
        return None

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open cover."""
        await self.set_home_endpoint_value(self._command_up, True)
        self._state = STATE_OPEN

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close cover."""
        await self.set_home_endpoint_value(self._command_down, True)
        self._state = STATE_CLOSED

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop cover."""
        await self.set_home_endpoint_value(self._command_stop, True)
        self._state = None

    async def async_update(self) -> None:
        """Get the state & name and update it."""
        node = self._router.home_devices[self._id]
        self._attr_name = node["label"].strip()
        self._state = self.convert_state(
            await self.get_home_endpoint_value(self._command_state)
        )

    def convert_state(self, state):
        """Convert the state to HA state."""
        if state:
            return STATE_CLOSED
        if state is not None:
            return STATE_OPEN
        return None

"""Regression tests for two startup failures that removed entities from HA.

1. ``select.zendure_manager_operation`` failed to add because
   ``ZendureRestoreSelect`` blindly trusted the restored state string. A state
   of ``unavailable``/``unknown`` (or a renamed option from an older release)
   left ``entity.value`` at ``None``, and ``ManagerMode(None)`` raised inside
   the ``async_added_to_hass`` callback. Self-perpetuating: once the entity
   fails to add, its state stays ``unavailable``, so every later restart
   restores ``unavailable`` and fails again.

2. The whole ACE 1500 device failed to load. The device publishes an MQTT
   property whose key is the empty string; ``entityUpdate`` turned that into a
   sensor with translation_key "" and unique_id "ace_1500". On the next reload
   ``check_entities`` tried to migrate it to "sensor.ace_1500_" -- a trailing
   underscore, which Home Assistant rejects -- and the resulting ValueError
   aborted construction of the entire device.
"""

from __future__ import annotations

import asyncio

import pytest

from custom_components.zendure_ha.const import ManagerMode
from custom_components.zendure_ha.entity import EntityDevice, snakecase
from custom_components.zendure_ha.select import ZendureRestoreSelect, ZendureSelect

MANAGER_OPTIONS = {0: "off", 1: "manual", 2: "smart", 3: "smart_discharging", 4: "smart_charging", 5: "store_solar"}


class FakeDevice:
    """Minimal EntityDevice surface used by EntityZendure.__init__."""

    def __init__(self, name: str = "Zendure Manager") -> None:
        self.name = name
        self.entities: dict = {}
        self.checkEntity: dict[str, str] = {}


@pytest.fixture(autouse=True)
def _headless(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make ZendureRestoreSelect constructible and awaitable without Home Assistant.

    ``super().async_added_to_hass()`` resolves to ZendureSelect in the MRO; the
    stubbed HA base classes give back a non-awaitable, so supply a real no-op.
    ``current_option`` is likewise a real SelectEntity property the stubs lack.
    """

    async def _noop(self) -> None:
        return None

    monkeypatch.setattr(ZendureSelect, "add", staticmethod(lambda _entities: None), raising=False)
    monkeypatch.setattr(ZendureSelect, "async_added_to_hass", _noop, raising=False)
    monkeypatch.setattr(ZendureSelect, "current_option", property(lambda self: self._attr_current_option), raising=False)


def restore(select: ZendureRestoreSelect, restored: str | None) -> ZendureRestoreSelect:
    """Run the real async_added_to_hass against a given restored state."""

    class State:
        state = restored

    async def _last_state():
        return None if restored is None else State()

    select.async_get_last_state = _last_state
    asyncio.run(select.async_added_to_hass())
    return select


@pytest.fixture
def select() -> ZendureRestoreSelect:
    """A manager-mode select built without Home Assistant."""
    return ZendureRestoreSelect(FakeDevice(), "Operation", MANAGER_OPTIONS, None)


# --- 1. restore must never yield an unmappable option ------------------------


@pytest.mark.parametrize("restored", ["unavailable", "unknown", "matching", "", None])
def test_restore_rejects_unmappable_state(select: ZendureRestoreSelect, restored: str | None) -> None:
    """A state that is not a current option must fall back, not poison .value.

    ``ManagerMode(None)`` raises, which killed the entity during add.
    """
    restore(select, restored)

    assert select.value is not None
    assert ManagerMode(select.value) is ManagerMode.OFF


@pytest.mark.parametrize("restored", list(MANAGER_OPTIONS.values()))
def test_restore_keeps_valid_state(select: ZendureRestoreSelect, restored: str) -> None:
    """A genuinely valid restored option is still honoured."""
    restore(select, restored)

    assert select._attr_current_option == restored
    assert ManagerMode(select.value).name is not None


def test_restore_falls_back_to_constructor_default() -> None:
    """When restore fails, the constructor's explicit default wins over options[0]."""
    sel = ZendureRestoreSelect(FakeDevice("Ace 1500"), "hubMode", {0: "paired", 1: "standalone"}, None, 1)

    restore(sel, "unavailable")

    assert sel._attr_current_option == "standalone"


def test_restore_still_fires_onchanged(select: ZendureRestoreSelect) -> None:
    """The callback must still run after a rejected restore, with a usable value."""
    seen: list = []

    async def onchanged(entity, _option) -> None:
        seen.append(ManagerMode(entity.value))

    select.onchanged = onchanged
    restore(select, "unavailable")

    assert seen == [ManagerMode.OFF]


# --- 2. keys with no usable characters must not become entities --------------


def test_entity_update_ignores_keys_that_snakecase_to_empty() -> None:
    """The ACE 1500 publishes an empty property key; it must not create a sensor.

    Such an entity gets translation_key "" and a unique_id that collapses onto
    the device name, which is what later makes check_entities build the invalid
    entity id "sensor.ace_1500_".
    """
    device = EntityDevice.__new__(EntityDevice)
    device.name = "Ace 1500"
    device.entities = {}

    assert snakecase("") == ""
    assert snakecase("-") == ""
    assert device.entityUpdate("", 5) is False
    assert device.entityUpdate("-", 5) is False
    assert device.entities == {}

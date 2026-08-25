"""Hardware bypass flag (byPass) — dispatch-capacity exclusion + no_alternative override.

A device can report a hardware bypass flag independently of its SoC state
(#1565: a not-full device reporting bypass and ignoring a raised outputLimit).
`dispatchable()` in power_discharge() excludes any such device from the
dispatchable capacity pool, unless every discharging device is bypassing and
no idle device is left to help (`no_alternative`), in which case the
exclusion is overridden so the deficit still gets covered.

Two testing styles live here: CSV-driven steady-state conformance for cases
that settle to a fixed point, and command-assertion tests (borrowing the bare
manager harness from test_manager_dispatch.py) for the idle-kickstart
transient that doesn't fit the steady-state model.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from custom_components.zendure_ha.const import DeviceState, ManagerMode

from ..test_manager_dispatch import _FakeDevice, _make_manager_harness
from .harness import Case, assert_matches_spec, drive_metered, load_cases_from_csv, make_params

CASES = load_cases_from_csv("bypass")


@pytest.mark.parametrize("case", make_params(CASES))
async def test_bypass_matches_spec(case: Case) -> None:
    devs = await drive_metered(ManagerMode[case.mode], case)

    assert_matches_spec(devs, case)


async def test_idle_alternative_keeps_bypassing_device_excluded() -> None:
    """A genuinely idle, not-full device is a real alternative to a bypassing
    device: no_alternative must stay False (via its self.idle check, not just
    the 'another discharging device has capacity' check already covered
    elsewhere), so the bypassing device stays excluded and the idle device is
    started instead of the bypassing one being forced out of bypass.
    """
    manager = _make_manager_harness()
    dev1 = _FakeDevice(pwr_max=1200, electric_level=50)
    dev1.byPass = SimpleNamespace(asInt=1)
    dev1.pwr_produced = -50
    dev2 = _FakeDevice(pwr_max=1200, electric_level=50)  # idle, not full (default state)

    manager.discharge = [dev1]
    manager.idle = [dev2]
    manager.idle_lvlmax = 50
    manager.discharge_weight = dev1.pwr_max * dev1.electricLevel.asInt
    manager.discharge_produced = 50

    await manager.power_discharge(100)

    assert dev1.discharge_calls == [0]  # excluded: dev2 is a real alternative
    assert dev2.discharge_calls == [50]  # idle device started, not the bypassing one


async def test_socempty_idle_device_is_not_a_real_alternative() -> None:
    """A SOCEMPTY idle device can't actually discharge, so it must not count as
    an alternative: no_alternative should still kick in and the bypassing
    device gets its normal (uncapped) share instead of being excluded.
    """
    manager = _make_manager_harness()
    dev1 = _FakeDevice(pwr_max=1200, electric_level=50)
    dev1.byPass = SimpleNamespace(asInt=1)
    dev1.pwr_produced = -50
    dev2 = _FakeDevice(pwr_max=1200, electric_level=50, state=DeviceState.SOCEMPTY)

    manager.discharge = [dev1]
    manager.idle = [dev2]
    manager.idle_lvlmax = 50
    manager.discharge_weight = dev1.pwr_max * dev1.electricLevel.asInt
    manager.discharge_produced = 50

    await manager.power_discharge(100)

    assert dev1.discharge_calls == [100]  # not excluded: dev2 can't actually help
    assert dev2.discharge_calls == []  # SOCEMPTY is never started

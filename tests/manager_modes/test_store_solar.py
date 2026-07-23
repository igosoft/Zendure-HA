"""STORE_SOLAR — manager-mode conformance against the spec CSV.

Sends all solar to the battery (never to home while P1 > 0); FULL bypasses.
On a HUB device it never grid-charges. All 39 rows conform.
"""

from __future__ import annotations

import pytest

from custom_components.zendure_ha.const import ManagerMode

from .harness import Case, drive_metered, load_cases_from_csv, make_params

CASES = load_cases_from_csv("store_solar")
DIVERGENCES: dict = {}  # fully conforms


@pytest.mark.parametrize("case", make_params(CASES, DIVERGENCES))
def test_store_solar_matches_spec(case: Case):
    dev = drive_metered(ManagerMode.STORE_SOLAR, case)

    assert dev.net_to_home == case.device_to_grid, "Device to grid"
    assert dev.batteryOutput.asInt == case.discharging, "Battery discharging"
    assert dev.batteryInput.asInt == case.charging, "Battery charging"

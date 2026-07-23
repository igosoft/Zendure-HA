"""MATCHING — manager-mode conformance against the spec CSV.

Balances P1 to zero using PV + battery; on a HUB device (no AC-charge path) it
never grid-charges, so negative-P1 rows just store the device's own solar. All
57 rows conform under the faithful residual-meter loop.
"""

from __future__ import annotations

import pytest

from custom_components.zendure_ha.const import ManagerMode

from .harness import Case, drive_metered, load_cases_from_csv, make_params

CASES = load_cases_from_csv("matching")
DIVERGENCES: dict = {}  # fully conforms


@pytest.mark.parametrize("case", make_params(CASES, DIVERGENCES))
def test_matching_matches_spec(case: Case):
    dev = drive_metered(ManagerMode.MATCHING, case)

    assert dev.net_to_home == case.device_to_grid, "Device to grid"
    assert dev.batteryOutput.asInt == case.discharging, "Battery discharging"
    assert dev.batteryInput.asInt == case.charging, "Battery charging"

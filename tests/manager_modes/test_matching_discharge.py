"""MATCHING_DISCHARGE — manager-mode conformance against the spec CSV.

`power_discharge(max(self.produced, setpoint))` — discharge only, NEVER charge:
all solar is always passed to home (surplus exported, not stored) and the battery
only covers the gap when demand exceeds PV.

Resolved design question A: MATCHING_DISCHARGE must not charge the battery, so
the spec (pass all solar to home) was right and the code was fixed to floor the
output at `self.produced` (it previously capped at P1 and stored the surplus).
All rows now conform.
"""

from __future__ import annotations

import pytest

from custom_components.zendure_ha.const import ManagerMode

from .harness import Case, drive_metered, load_cases_from_csv, make_params

CASES = load_cases_from_csv("matching_discharge")

DIVERGENCES: dict = {}  # resolved: code fixed to never charge (floor at self.produced)


@pytest.mark.parametrize("case", make_params(CASES, DIVERGENCES))
def test_matching_discharge_matches_spec(case: Case):
    dev = drive_metered(ManagerMode.MATCHING_DISCHARGE, case)

    assert dev.net_to_home == case.device_to_grid, "Device to grid"
    assert dev.batteryOutput.asInt == case.discharging, "Battery discharging"
    assert dev.batteryInput.asInt == case.charging, "Battery charging"

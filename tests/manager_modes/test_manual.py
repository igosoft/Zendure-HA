"""MANUAL — manager-mode conformance against the spec CSV.

The device outputs/draws exactly the manual power (P1 ignored). Negative power
grid-charges, so this mode is driven on an AC-capable device (Hyper2000). All
positive/zero rows and the |power| > 50 grid-charge rows conform.
"""

from __future__ import annotations

import pytest

from custom_components.zendure_ha.const import ManagerMode

from .harness import Case, drive_metered, load_cases_from_csv, make_params

CASES = load_cases_from_csv("manual")

# Previously an off-by-one at the boundary: after the charge hysteresis zeroed the
# device on the first cycle, restarting grid charge went through the idle-charge
# guard `setpoint < -POWER_START` (strict), so exactly -50 W never restarted and only
# own solar was stored. Fixed in manager.py to `<=` — all rows now conform.
DIVERGENCES: dict = {}


@pytest.mark.parametrize("case", make_params(CASES, DIVERGENCES))
def test_manual_matches_spec(case: Case):
    dev = drive_metered(ManagerMode.MANUAL, case)

    assert dev.net_to_home == case.device_to_grid, "Device to grid"
    assert dev.batteryOutput.asInt == case.discharging, "Battery discharging"
    assert dev.batteryInput.asInt == case.charging, "Battery charging"

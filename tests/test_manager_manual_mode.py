"""
Tests for MANUAL mode power distribution in ZendureManager.

Covers:
  1. Mode dispatch: powerChanged routes manualpower to power_discharge / power_charge.
  2. SOCFULL solar passthrough: SOCFULL devices output exactly their solar production,
     overriding the manual setpoint so the battery is never drained.
"""

from datetime import datetime

from custom_components.zendure_ha.const import DeviceState, ManagerMode
from custom_components.zendure_ha.manager import ZendureManager

from .conftest import _run, _device, _manager


# ---------------------------------------------------------------------------
# Helpers for distribution tests
# ---------------------------------------------------------------------------

def _setup_distribution(*, pwr_produced: int, state: DeviceState, electricLevel: int = 100,
                        in_idle: bool = False):
    """
    Create a manager and a single device ready for power_discharge testing.

    The manager has the real power_discharge method (not mocked) and all the
    accumulator attributes that the method reads.
    """
    mgr = _manager(operation=ManagerMode.MANUAL)
    # Remove the mocked power_discharge so the real method runs
    del mgr.power_discharge

    d = _device(state=state, electricLevel=electricLevel, pwr_max=1200)
    d.pwr_produced = pwr_produced

    if in_idle:
        mgr.idle = [d]
        mgr.idle_lvlmax = electricLevel
    else:
        mgr.discharge = [d]
        mgr.discharge_limit = d.fuseGrp.discharge_limit(d)
        mgr.discharge_weight = d.pwr_max * electricLevel
        mgr.discharge_produced = -pwr_produced  # positive = solar watts
        mgr.discharge_optimal = d.discharge_optimal

    return mgr, d


# ---------------------------------------------------------------------------
# Tests: mode dispatch
# ---------------------------------------------------------------------------

class TestManualModeDispatch:
    """Verify powerChanged dispatches to the correct method in MANUAL mode."""

    def test_manual_positive_calls_power_discharge(self):
        """Manual power > 0 → power_discharge(manualpower)."""
        async def _inner():
            mgr = _manager(operation=ManagerMode.MANUAL)
            mgr.manualpower.asNumber = 300
            await ZendureManager.powerChanged(mgr, p1=100, isFast=False,
                                              time=datetime.now())
            mgr.power_discharge.assert_called_once_with(300)
            mgr.power_charge.assert_not_called()
        _run(_inner())

    def test_manual_negative_calls_power_charge(self):
        """Manual power < 0 → power_charge(manualpower)."""
        async def _inner():
            mgr = _manager(operation=ManagerMode.MANUAL)
            mgr.manualpower.asNumber = -500
            now = datetime.now()
            await ZendureManager.powerChanged(mgr, p1=100, isFast=False,
                                              time=now)
            mgr.power_charge.assert_called_once_with(-500, now)
            mgr.power_discharge.assert_not_called()
        _run(_inner())

    def test_manual_zero_calls_power_charge(self):
        """Manual power == 0 → power_charge(0) (not discharge)."""
        async def _inner():
            mgr = _manager(operation=ManagerMode.MANUAL)
            mgr.manualpower.asNumber = 0
            now = datetime.now()
            await ZendureManager.powerChanged(mgr, p1=100, isFast=False,
                                              time=now)
            mgr.power_charge.assert_called_once_with(0, now)
            mgr.power_discharge.assert_not_called()
        _run(_inner())


# ---------------------------------------------------------------------------
# Tests: SOCFULL solar passthrough in power_discharge
# ---------------------------------------------------------------------------

class TestManualModeWithSocfull:
    """
    Verify that in MANUAL mode, power_discharge respects SOCFULL constraints:
    SOCFULL devices output only their solar production, never draining the battery.
    """

    # ---- Row 1: PV=200W, SoC NOT full, discharging=100W, manual=300W ----

    def test_not_full_pv200_output_300(self):
        """Row 1: PV=200, not SOCFULL → full manual power (300W)."""
        async def _inner():
            mgr, d = _setup_distribution(pwr_produced=-200,
                                         state=DeviceState.INACTIVE,
                                         electricLevel=50)
            await ZendureManager.power_discharge(mgr, 300)
            d.power_discharge.assert_called_once_with(300)
        _run(_inner())

    # ---- Row 2: PV=200W, SoC FULL, discharging=0W, manual=300W ----

    def test_socfull_pv200_output_200(self):
        """Row 2: PV=200, SOCFULL → commanded the full manual (300W). The SOCFULL cap
        only raises pwr *up* to solar, never down, and min(pwr, setpoint) keeps it at
        300; the full battery bypasses to its 200 W solar (no drain), so steady-state
        output is 200 W — the no-drain protection is at the hardware-bypass level (see
        the FULL rows in matching.csv), not the commanded value."""
        async def _inner():
            mgr, d = _setup_distribution(pwr_produced=-200,
                                         state=DeviceState.SOCFULL,
                                         electricLevel=100)
            await ZendureManager.power_discharge(mgr, 300)
            d.power_discharge.assert_called_once_with(300)
        _run(_inner())

    # ---- Row 3: PV=50W, SoC NOT full, discharging=250W, manual=300W ----

    def test_not_full_pv50_output_300(self):
        """Row 3: PV=50, not SOCFULL → full manual power (300W)."""
        async def _inner():
            mgr, d = _setup_distribution(pwr_produced=-50,
                                         state=DeviceState.INACTIVE,
                                         electricLevel=50)
            await ZendureManager.power_discharge(mgr, 300)
            d.power_discharge.assert_called_once_with(300)
        _run(_inner())

    # ---- Row 4: PV=50W, SoC FULL, discharging=0W, manual=300W ----

    def test_socfull_pv50_output_50(self):
        """Row 4: PV=50, SOCFULL → commanded the full manual (300W); the full battery
        bypasses to its 50 W solar (no drain). Command != solar; outcome = 50 W."""
        async def _inner():
            mgr, d = _setup_distribution(pwr_produced=-50,
                                         state=DeviceState.SOCFULL,
                                         electricLevel=100)
            await ZendureManager.power_discharge(mgr, 300)
            d.power_discharge.assert_called_once_with(300)
        _run(_inner())

    # ---- Row 5: PV=0W, SoC NOT full, discharging=300W, manual=300W ----

    def test_not_full_pv0_output_300(self):
        """Row 5: PV=0, not SOCFULL → full manual power (300W)."""
        async def _inner():
            mgr, d = _setup_distribution(pwr_produced=0,
                                         state=DeviceState.INACTIVE,
                                         electricLevel=50)
            await ZendureManager.power_discharge(mgr, 300)
            d.power_discharge.assert_called_once_with(300)
        _run(_inner())

    # ---- Row 6: PV=0W, SoC FULL, discharging=0W, manual=300W ----

    def test_socfull_pv0_output_0(self):
        """Row 6: PV=0, SOCFULL, idle → the idle-start kickstart fires POWER_START (50W)
        because it only skips SOCEMPTY, not SOCFULL; a full battery with no solar
        outputs 0 W, so the kickstart is a no-op at the hardware level."""
        async def _inner():
            mgr, d = _setup_distribution(pwr_produced=0,
                                         state=DeviceState.SOCFULL,
                                         electricLevel=100,
                                         in_idle=True)
            await ZendureManager.power_discharge(mgr, 300)
            d.power_discharge.assert_called_once_with(50)
        _run(_inner())

    # ---- Row 7: PV=500W, SoC NOT full, discharging=0W, charging=200W, manual=300W ----

    def test_not_full_pv500_charging_output_300(self):
        """Row 7: PV=500, battery charging 200W from solar, net homeOutput=300
        → device in discharge list, gets full manual 300W."""
        async def _inner():
            mgr, d = _setup_distribution(pwr_produced=-500,
                                         state=DeviceState.INACTIVE,
                                         electricLevel=50)
            await ZendureManager.power_discharge(mgr, 300)
            d.power_discharge.assert_called_once_with(300)
        _run(_inner())

    # ---- Row 8: PV=500W, SoC FULL, discharging=0W, manual=300W ----

    def test_socfull_pv500_output_500(self):
        """Row 8: PV=500, SOCFULL → commanded the manual setpoint (300W, held by
        min(pwr, setpoint)); the full battery still bypasses all 500 W solar to home,
        so the steady-state output is 500 W (solar cannot be turned off)."""
        async def _inner():
            mgr, d = _setup_distribution(pwr_produced=-500,
                                         state=DeviceState.SOCFULL,
                                         electricLevel=100)
            await ZendureManager.power_discharge(mgr, 300)
            d.power_discharge.assert_called_once_with(300)
        _run(_inner())

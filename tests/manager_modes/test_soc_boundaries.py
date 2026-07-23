"""SoC boundary tests — socSet, minSoc thresholds and the socSet=0 kill-switch.

These are mode-agnostic: they test classification and distribution at SoC
boundaries. MATCHING mode is used as the representative mode.
"""

from datetime import datetime
from custom_components.zendure_ha.const import ManagerMode, DeviceState
from custom_components.zendure_ha.manager import ZendureManager
from tests.conftest import _run, _device, _manager, _sensor

MODE = ManagerMode.MATCHING


class TestSocBoundaries:
    """SoC threshold tests across modes."""

    def test_socset_80_elevel_80_is_full(self):
        """S1: socSet=80, eLevel=80 → SOCFULL (>= boundary exactly at threshold)."""
        async def _inner():
            d = _device(state=DeviceState.SOCFULL, homeOutput=200, electricLevel=80)
            d.socSet = _sensor(80)
            mgr = _manager(operation=MODE, devices=[d])
            await ZendureManager.powerChanged(mgr, p1=100, isFast=False, time=datetime.now())
            # eLevel(80) >= socSet(80) → SOCFULL. The bypass (200 W) is removed from
            # the dispatchable setpoint (100 + 200 - 200 = 100), and the SOCFULL solar
            # cap is re-capped by min(pwr, setpoint) back to 100. The full battery still
            # bypasses all 200 W solar to home, so steady-state Device-to-grid = 200
            # (see matching.csv r73) — only the commanded value is 100.
            d.power_discharge.assert_called_with(100)
        _run(_inner())

    def test_socset_80_elevel_79_is_not_full(self):
        """S2: socSet=80, eLevel=79 → INACTIVE (79 < 80, not full)."""
        async def _inner():
            d = _device(state=DeviceState.INACTIVE, homeOutput=200, electricLevel=79)
            d.socSet = _sensor(80)
            mgr = _manager(operation=MODE, devices=[d])
            await ZendureManager.powerChanged(mgr, p1=100, isFast=False, time=datetime.now())
            # eLevel(79) < socSet(80) → INACTIVE → no SOCFULL cap
            # Gets normal discharge for P1=100 with homeOutput=200
            # setpoint = 100 + 200 = 300 → device gets 300
            assert d.power_discharge.called
        _run(_inner())

    def test_minsoc_20_elevel_20_is_empty(self):
        """S3: minSoc=20, eLevel=20 → SOCEMPTY (<= boundary, exactly at threshold)."""
        async def _inner():
            d = _device(state=DeviceState.SOCEMPTY, homeOutput=0, homeInput=0,
                        electricLevel=20)
            d.minSoc = _sensor(20)
            mgr = _manager(operation=MODE, devices=[d])
            await ZendureManager.powerChanged(mgr, p1=100, isFast=False, time=datetime.now())
            # eLevel(20) <= minSoc(20) → SOCEMPTY → idle, should NOT discharge
            d.power_discharge.assert_not_called()
        _run(_inner())

    def test_minsoc_20_elevel_21_is_not_empty(self):
        """S4: minSoc=20, eLevel=21 → INACTIVE (21 > 20, not empty), kickstarted."""
        async def _inner():
            d = _device(state=DeviceState.INACTIVE, homeOutput=0, electricLevel=21)
            d.minSoc = _sensor(20)
            mgr = _manager(operation=MODE, devices=[d])
            await ZendureManager.powerChanged(mgr, p1=100, isFast=False, time=datetime.now())
            # eLevel(21) > minSoc(20) → INACTIVE, not empty → idle but kickstarted
            # Idle start fires POWER_START=50W because state isn't SOCEMPTY/SOCFULL
            d.power_discharge.assert_called_with(50)
        _run(_inner())

    def test_socset_zero_device_offline(self):
        """S5: socSet=0 → OFFLINE, device skipped entirely (kill-switch)."""
        async def _inner():
            d = _device(state=DeviceState.INACTIVE, homeOutput=300, electricLevel=50)
            d.socSet = _sensor(0)
            d.power_get.return_value = False  # socSet=0 triggers OFFLINE in power_get
            mgr = _manager(operation=MODE, devices=[d])
            await ZendureManager.powerChanged(mgr, p1=100, isFast=False, time=datetime.now())
            d.power_discharge.assert_not_called()
            d.power_charge.assert_not_called()
        _run(_inner())

    def test_minsoc_20_elevel_30_weighting_skew(self):
        """S6: minSoc=20, eLevel=30 → INACTIVE, weighting uses raw 30% not usable 10%.

        With homeOutput=0 the device lands in idle, but the idle-start
        kickstart still fires because state is INACTIVE (not SOCEMPTY/SOCFULL).
        The weighting note applies when the device is actively discharging.
        """
        async def _inner():
            d = _device(state=DeviceState.INACTIVE, homeOutput=0, homeInput=0,
                        electricLevel=30)
            d.minSoc = _sensor(20)
            mgr = _manager(operation=MODE, devices=[d])
            await ZendureManager.powerChanged(mgr, p1=100, isFast=False, time=datetime.now())
            # eLevel(30) > minSoc(20) → INACTIVE, not empty → kickstarted with 50W
            # If this device were in the discharge list, its weight = pwr_max * 30
            # (raw eLevel), NOT pwr_max * (30-20) = pwr_max * 10
            d.power_discharge.assert_called_with(50)
        _run(_inner())

    def test_socset_80_elevel_80_pv200_passthrough(self):
        """S7: SOCFULL at 80% with PV=200W — solar passthrough still applies."""
        async def _inner():
            d = _device(state=DeviceState.SOCFULL, homeOutput=200, electricLevel=80)
            d.socSet = _sensor(80)
            mgr = _manager(operation=MODE, devices=[d])
            await ZendureManager.powerChanged(mgr, p1=100, isFast=False, time=datetime.now())
            # SOCFULL at 80%, PV=200. Dispatchable setpoint = 100 (bypass removed), so
            # the command is 100; the full battery still bypasses all 200 W solar to
            # home (steady-state Device-to-grid = 200, see matching.csv r73).
            d.power_discharge.assert_called_with(100)
        _run(_inner())

    def test_minsoc_20_elevel_20_manual_discharge_blocked(self):
        """S8: SOCEMPTY at 20% with manual discharge → blocked."""
        async def _inner():
            d = _device(state=DeviceState.SOCEMPTY, homeOutput=0, electricLevel=20)
            d.minSoc = _sensor(20)
            mgr = _manager(operation=ManagerMode.MANUAL, devices=[d])
            mgr.manualpower.asNumber = 300
            await ZendureManager.powerChanged(mgr, p1=0, isFast=False, time=datetime.now())
            # eLevel(20) <= minSoc(20) → SOCEMPTY → idle
            # Manual discharge 300W should NOT happen (battery empty)
            d.power_discharge.assert_not_called()
        _run(_inner())

"""
Tests for the SOCFULL solar bypass fix in powerChanged() and power_charge().

Bug: when a device (e.g. Hub2000) reaches 100% SOC but still passes solar to
home via homeOutput, the old code added that homeOutput to the setpoint and then
subtracted it again via the discharge_bypass correction — but the correction was
clamped to 0 when p1 >= 0.  At equilibrium (p1 == 0, Hub solar == SF2400AC
charge rate) the net setpoint was 0 instead of negative, so power_charge(0)
stopped the SF2400ACs.

Fix:
  1. Don't add SOCFULL + exports_bypass device homeOutput to the setpoint at all.
  2. Don't stop SOCFULL + exports_bypass devices in the power_charge() stop-loop;
     their solar must keep flowing so the charge loop can absorb it.
"""

from datetime import datetime
from unittest.mock import AsyncMock

from custom_components.zendure_ha.const import DeviceState, ManagerMode
from custom_components.zendure_ha.manager import ZendureManager

from .conftest import _run, _sensor, _device, _manager


# ---------------------------------------------------------------------------
# Tests: setpoint calculation in powerChanged()
# ---------------------------------------------------------------------------

class TestSetpointCalculation:
    """SOCFULL homeOutput must not inflate the setpoint."""

    def test_socfull_homeoutput_excluded_from_setpoint(self):
        """
        Core regression test.

        At equilibrium (p1=0, Hub solar 800W == SF2400AC charging 400W+400W)
        the setpoint must be -800W so power_charge keeps the SF2400ACs running.

        Old behaviour:  setpoint = 0 + 800(Hub) - 400 - 400 = 0  → power_charge(0)  → STOP
        New behaviour:  setpoint = 0            - 400 - 400 = -800 → power_charge(-800) → OK
        """
        async def _inner():
            hub = _device(name="Hub2000", state=DeviceState.SOCFULL, exports_bypass=True,
                          homeOutput=800, electricLevel=100)
            sf1 = _device(name="SF2400-1", homeInput=400, batteryInput=400)
            sf2 = _device(name="SF2400-2", homeInput=400, batteryInput=400)

            mgr = _manager(operation=ManagerMode.STORE_SOLAR, devices=[hub, sf1, sf2])
            await ZendureManager.powerChanged(mgr, p1=0, isFast=False, time=datetime.now())

            # Categorisation sanity checks
            assert hub in mgr.discharge
            assert sf1 in mgr.charge
            assert sf2 in mgr.charge

            mgr.power_charge.assert_called_once()
            setpoint_used = mgr.power_charge.call_args[0][0]
            assert setpoint_used == -800, (
                f"SOCFULL homeOutput must not be credited to setpoint; "
                f"expected -800W, got {setpoint_used}W"
            )

        _run(_inner())

    def test_non_socfull_homeoutput_included_in_setpoint(self):
        """Non-SOCFULL discharge device homeOutput IS credited (unchanged behaviour)."""
        async def _inner():
            discharger = _device(name="SF2400", homeOutput=800, electricLevel=60)

            mgr = _manager(operation=ManagerMode.MATCHING, devices=[discharger])
            await ZendureManager.powerChanged(mgr, p1=-200, isFast=False, time=datetime.now())

            # setpoint = -200(p1) + 800(homeOutput) = +600 → power_discharge(600)
            mgr.power_discharge.assert_called_once()
            setpoint_used = mgr.power_discharge.call_args[0][0]
            assert setpoint_used == 600

        _run(_inner())

    def test_socfull_exports_bypass_false_includes_homeoutput(self):
        """
        SOCFULL device with exports_bypass=False keeps old behaviour:
        homeOutput IS added to setpoint.
        """
        async def _inner():
            hub = _device(name="Hub", state=DeviceState.SOCFULL, exports_bypass=False,
                          homeOutput=800, electricLevel=100)

            mgr = _manager(operation=ManagerMode.MATCHING, devices=[hub])
            await ZendureManager.powerChanged(mgr, p1=-200, isFast=False, time=datetime.now())

            mgr.power_discharge.assert_called_once()
            setpoint_used = mgr.power_discharge.call_args[0][0]
            assert setpoint_used == 600

        _run(_inner())

    def test_socfull_with_no_homeoutput_goes_to_idle(self):
        """SOCFULL device with homeOutput=0 (solar curtailed) lands in idle."""
        async def _inner():
            hub = _device(name="Hub2000", state=DeviceState.SOCFULL, exports_bypass=True,
                          homeOutput=0, electricLevel=100)
            sf1 = _device(name="SF2400-1", homeInput=400, batteryInput=400)

            mgr = _manager(operation=ManagerMode.STORE_SOLAR, devices=[hub, sf1])
            await ZendureManager.powerChanged(mgr, p1=-400, isFast=False, time=datetime.now())

            assert hub in mgr.idle
            assert sf1 in mgr.charge

            # setpoint = -400(p1) - 400(sf1) = -800; STORE_SOLAR: power_charge(min(0,-800))
            mgr.power_charge.assert_called_once()
            setpoint_used = mgr.power_charge.call_args[0][0]
            assert setpoint_used == -800

        _run(_inner())

    def test_matching_charge_mode_also_fixed(self):
        """The fix applies equally to MATCHING_CHARGE (same case block)."""
        async def _inner():
            hub = _device(name="Hub2000", state=DeviceState.SOCFULL, exports_bypass=True,
                          homeOutput=600, electricLevel=100)
            sf1 = _device(name="SF2400-1", homeInput=300, batteryInput=300)
            sf2 = _device(name="SF2400-2", homeInput=300, batteryInput=300)

            mgr = _manager(operation=ManagerMode.MATCHING_CHARGE, devices=[hub, sf1, sf2])
            await ZendureManager.powerChanged(mgr, p1=0, isFast=False, time=datetime.now())

            # setpoint = 0 - 300 - 300 = -600 → power_charge(-600)
            mgr.power_charge.assert_called_once()
            setpoint_used = mgr.power_charge.call_args[0][0]
            assert setpoint_used == -600

        _run(_inner())


# ---------------------------------------------------------------------------
# Tests: stop-loop in power_charge()
# ---------------------------------------------------------------------------

class TestPowerChargeStopLoop:
    """SOCFULL + exports_bypass devices must not be stopped in power_charge()."""

    def test_socfull_exports_bypass_device_not_stopped(self):
        """Hub2000 (SOCFULL, exports_bypass=True) must NOT receive power_discharge(0)."""
        async def _inner():
            # A SOCFULL device passing 800 W solar to home is in hardware bypass
            # (byPass > 0); the current stop-loop skips such devices by byPass.asInt,
            # so it is not stopped.
            hub = _device(name="Hub2000", state=DeviceState.SOCFULL, exports_bypass=True,
                          homeOutput=800, bypass=2)
            mgr = _manager()
            mgr.discharge = [hub]

            await ZendureManager.power_charge(mgr, -800, datetime.now())

            hub.power_discharge.assert_not_called()

        _run(_inner())

    def test_non_socfull_device_is_stopped(self):
        """Non-SOCFULL discharge device must be stopped (unchanged behaviour)."""
        async def _inner():
            sf = _device(name="SF2400", homeOutput=400)
            mgr = _manager()
            mgr.discharge = [sf]

            await ZendureManager.power_charge(mgr, -800, datetime.now())

            sf.power_discharge.assert_called_once_with(0)

        _run(_inner())

    def test_socfull_exports_bypass_false_is_stopped(self):
        """SOCFULL + exports_bypass=False falls back to old behaviour: IS stopped."""
        async def _inner():
            hub = _device(name="Hub", state=DeviceState.SOCFULL, exports_bypass=False,
                          homeOutput=800)
            mgr = _manager()
            mgr.discharge = [hub]

            await ZendureManager.power_charge(mgr, -800, datetime.now())

            hub.power_discharge.assert_called_once_with(0)

        _run(_inner())

    def test_mixed_discharge_list(self):
        """Hub (SOCFULL+bypass) kept running; SF2400 (non-SOCFULL) stopped."""
        async def _inner():
            hub = _device(name="Hub2000", state=DeviceState.SOCFULL, exports_bypass=True,
                          homeOutput=800, bypass=2)  # bypassing device → byPass>0, kept running
            sf = _device(name="SF2400", homeOutput=400)
            mgr = _manager()
            mgr.discharge = [hub, sf]

            await ZendureManager.power_charge(mgr, -800, datetime.now())

            hub.power_discharge.assert_not_called()
            sf.power_discharge.assert_called_once_with(0)

        _run(_inner())

    def test_hardware_bypass_still_skipped(self):
        """byPass.asInt > 0 skip unchanged (pre-existing behaviour)."""
        async def _inner():
            dev = _device(name="Bypassing", homeOutput=400, bypass=1)
            mgr = _manager()
            mgr.discharge = [dev]

            await ZendureManager.power_charge(mgr, -800, datetime.now())

            dev.power_discharge.assert_not_called()

        _run(_inner())

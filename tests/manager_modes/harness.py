"""Headless harness driving the REAL ZendureManager against a fake device.

The spec CSVs (tests/manager_modes/<mode>.csv) describe the steady-state
hardware outcome (Battery Discharging / Charging / Device-to-grid) for a single
device given input (P1 / manual), PV and SoC. We test the manager as a control
law: initialise the device at the spec's steady state, run one real
``powerChanged`` cycle through a physical battery plant model, and assert the
system stays at the spec values (fixed-point / conformance test).
"""

from __future__ import annotations

import asyncio
import csv
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from custom_components.zendure_ha.const import DeviceState, ManagerMode
from custom_components.zendure_ha.manager import ZendureManager

CSV_DIR = Path(__file__).resolve().parent

# SoC label (spec) -> concrete DeviceState + a representative electricLevel %.
SOC = {
    "EMPTY": (DeviceState.SOCEMPTY, 5),
    "FULL": (DeviceState.SOCFULL, 100),
    "not full": (DeviceState.INACTIVE, 50),
}
SOC_ALL = ("EMPTY", "FULL", "not full")  # expansion for `any` rows


class _Sensor:
    """Minimal stand-in for a Zendure entity exposing .asInt / .asNumber."""

    def __init__(self, value: float = 0) -> None:
        self.value = value

    @property
    def asInt(self) -> int:  # noqa: N802 - mirror production API
        return int(self.value)

    @property
    def asNumber(self) -> float:  # noqa: N802
        return self.value


class _Recorder:
    """Captures manager entity writes without needing Home Assistant."""

    def __init__(self) -> None:
        self.value = None

    def update_value(self, value) -> bool:
        self.value = value
        return True


class FakeFuseGroup:
    """Single-device fuse group: mirrors FuseGroup.*_limit for one device."""

    def __init__(self, maxpower: int = 3600, minpower: int = -3600) -> None:
        self.maxpower = maxpower
        self.minpower = minpower
        self.initPower = True

    def discharge_limit(self, d: "FakeDevice") -> int:
        d.pwr_max = min(self.maxpower, d.discharge_limit)
        return d.pwr_max

    def charge_limit(self, d: "FakeDevice") -> int:
        d.pwr_max = max(self.minpower, d.charge_limit)
        return d.pwr_max


class FakeDevice:
    """Duck-typed device that plays the exact surface powerChanged/power_discharge use.

    ``power_discharge`` / ``power_charge`` apply a physical battery plant model so
    the resulting sensors reflect what real hardware would settle to for the
    commanded setpoint, PV and SoC.
    """

    def __init__(self, soc_state: DeviceState, level: int, pv: int,
                 discharge_limit: int = 1200, charge_limit: int = -1200,
                 min_output: int = 0) -> None:
        self.state = soc_state
        self.pv = pv
        self.discharge_limit = discharge_limit
        self.charge_limit = charge_limit
        self.discharge_optimal = discharge_limit // 4
        self.discharge_start = discharge_limit // 10
        self.charge_optimal = charge_limit // 4
        self.pwr_max = discharge_limit
        self.minOutput = min_output
        self.exports_bypass = True
        self.pwr_offgrid = 0
        self.pwr_produced = 0
        self.kWh = 2.0
        self.actualKwh = 1.0
        self.fuseGrp = FakeFuseGroup()

        self.solarInput = _Sensor(pv)
        self.homeOutput = _Sensor(0)
        self.homeInput = _Sensor(0)
        self.batteryOutput = _Sensor(0)   # packInputPower: battery -> out (discharge)
        self.batteryInput = _Sensor(0)    # outputPackPower: into battery (charge)
        self.electricLevel = _Sensor(level)
        self.byPass = _Sensor(0)

        self.commands: list[tuple[str, int]] = []

    @property
    def online(self) -> bool:
        return True

    async def power_get(self) -> bool:
        return True  # state is fixed for the scenario

    def seed_neutral(self) -> None:
        """Neutral start: device just passes its own solar, battery idle.

        We deliberately do NOT pre-seed the spec answer — the manager must drive
        the system to the spec value itself, so a 'manager does nothing' bug is
        caught rather than masked.
        """
        self.homeOutput.value = self.pv
        self.homeInput.value = 0
        self.batteryOutput.value = 0
        self.batteryInput.value = 0
        self.solarInput.value = self.pv

    def seed_spec(self, discharging: int, charging: int, device_to_grid: int) -> None:
        """Place the device at the spec's steady-state operating point."""
        self.homeOutput.value = max(0, device_to_grid)
        self.homeInput.value = max(0, -device_to_grid)   # negative grid = drawing from grid
        self.batteryOutput.value = discharging
        self.batteryInput.value = charging
        self.solarInput.value = self.pv

    def state_tuple(self) -> tuple[int, int, int]:
        return (self.homeOutput.asInt, self.batteryOutput.asInt, self.batteryInput.asInt)

    @property
    def net_to_home(self) -> int:
        """Net power the device delivers to the home bus (negative = drawing grid)."""
        return self.homeOutput.asInt - self.homeInput.asInt

    def _apply_net(self, target: int) -> None:
        """Unified battery plant: `target` = commanded NET power to the home bus
        (discharge > 0, charge < 0). One consistent physics for every mode:

          * solar always flows first; the battery makes up a discharge gap or
            absorbs whatever solar is left over (store), never wasting it;
          * grid is drawn only when the command asks for more than solar (T<0
            below -PV, or a discharge the battery can't reach);
          * FULL only bypasses solar to home; EMPTY can't discharge the battery.
        """
        pv = self.pv
        if self.state == DeviceState.SOCFULL:
            net, bat_in, bat_out = pv, 0, 0            # bypass only
        elif self.state == DeviceState.SOCEMPTY and target > pv:
            net, bat_in, bat_out = pv, 0, 0            # can't discharge past solar
        else:
            net = target
            bat_in = max(0, pv - target)               # surplus solar (+grid if T<0) stored
            bat_out = max(0, target - pv)              # battery covers the gap
        self.homeOutput.value = max(0, net)
        self.homeInput.value = max(0, -net)
        self.batteryInput.value = bat_in
        self.batteryOutput.value = bat_out

    async def power_discharge(self, power: int) -> int:
        out = max(0, min(power, self.discharge_limit))   # mirror device.power_discharge clamp
        self.commands.append(("discharge", power))
        self._apply_net(out)
        return self.homeOutput.asInt

    async def power_charge(self, power: int) -> int:
        chg = min(0, max(power, self.charge_limit))      # mirror device.power_charge clamp
        self.commands.append(("charge", power))
        self._apply_net(chg)
        return chg


def build_manager(mode: ManagerMode, device: FakeDevice) -> ZendureManager:
    mgr = object.__new__(ZendureManager)  # bypass HA-coupled __init__
    mgr.operation = mode
    mgr.devices = [device]
    mgr.simulation = False
    # manager entities -> recorders
    mgr.power = _Recorder()
    mgr.availableKwh = _Recorder()
    mgr.globalSoc = _Recorder()
    mgr.operationstate = _Recorder()
    # hysteresis / distribution state
    mgr.charge_time = datetime.max
    mgr.charge_last = datetime.min
    mgr.pwr_low = 0
    return mgr


def run_step(mgr: ZendureManager, p1: int, time: datetime | None = None) -> None:
    """Reset per-cycle accumulators (as _p1_changed does) then run one real cycle.

    ``time`` drives the manager's charge hysteresis (``charge_time = time + 2s``);
    callers doing a settling loop must advance it by >2s per cycle or charging
    never releases.
    """
    if time is None:
        time = datetime.now()
    mgr.charge = []
    mgr.charge_limit = 0
    mgr.charge_optimal = 0
    mgr.charge_weight = 0
    mgr.discharge = []
    mgr.discharge_bypass = 0
    mgr.discharge_limit = 0
    mgr.discharge_optimal = 0
    mgr.discharge_produced = 0
    mgr.discharge_weight = 0
    mgr.idle = []
    mgr.idle_lvlmax = 0
    mgr.idle_lvlmin = 100
    mgr.produced = 0
    for d in mgr.devices:
        d.fuseGrp.initPower = True
    asyncio.run(mgr.powerChanged(p1, False, time))


def run_to_steady_state(mgr: ZendureManager, p1: int, max_cycles: int = 15) -> int:
    """Run repeated P1 updates until the device sensors stop changing.

    Real hardware settles over several P1 ticks (an idle device is first woken
    at POWER_START, then ramped). Returns the number of cycles taken; if it does
    not converge, the caller's assertions surface the instability.
    """
    prev = [d.state_tuple() for d in mgr.devices]
    for cycle in range(1, max_cycles + 1):
        run_step(mgr, p1)
        cur = [d.state_tuple() for d in mgr.devices]
        if cur == prev:
            return cycle
        prev = cur
    return max_cycles


def drive_metered(mode: ManagerMode, case: "Case", cycles: int = 60) -> FakeDevice:
    """Faithful driver: seed the device at the spec state, then close the loop
    through a RESIDUAL P1 meter (Shelly 3EM at the grid: p1 = load - net) and run
    real ``powerChanged`` cycles. Assert the spec state is a stable equilibrium.

    MANUAL ignores P1 (uses manualpower); every other mode balances the load.
    """
    state, level = SOC[case.soc]
    # Model the user's hardware: smart modes run on a HUB (no AC-charge path,
    # charge_limit=0) so they can never grid-charge; MANUAL's negative-power rows
    # assume an AC-capable device (Hyper2000, charge_limit=-1200).
    charge_limit = -1200 if mode == ManagerMode.MANUAL else 0
    dev = FakeDevice(state, level, pv=case.pv, charge_limit=charge_limit)
    dev.seed_spec(case.discharging, case.charging, case.device_to_grid)
    mgr = build_manager(mode, dev)
    if mode == ManagerMode.MANUAL:
        mgr.manualpower = _Sensor(case.p1)          # input_w is the manual power
    load = 0 if mode == ManagerMode.MANUAL else case.p1
    base = datetime(2026, 1, 1, 0, 0, 0)
    for i in range(cycles):
        # advance wall-clock >2s/cycle so the charge hysteresis releases
        run_step(mgr, load - dev.net_to_home, base + timedelta(seconds=120 * i))
    return dev


@dataclass
class Case:
    mode: str
    num: int
    p1: int
    pv: int
    soc: str          # concrete SoC label (any-rows already expanded)
    discharging: int
    charging: int
    device_to_grid: int
    notes: str
    any_row: bool = False

    @property
    def id(self) -> str:
        star = "*" if self.any_row else ""
        return f"{self.mode}-r{self.num}-p1={self.p1}-pv={self.pv}-{self.soc}{star}"


def make_params(cases: list["Case"], divergences: dict) -> list:
    """Build pytest params, xfailing rows that are known code<->spec divergences.

    ``divergences`` keys may be a bare case number (applies to every SoC of that
    row) or a ``(num, soc)`` tuple (that SoC only). ``strict=True`` so the day the
    code is fixed the xfail turns into an XPASS failure and forces us to update.
    """
    import pytest

    params = []
    for c in cases:
        reason = divergences.get((c.num, c.soc)) or divergences.get(c.num)
        marks = [pytest.mark.xfail(reason=reason, strict=True)] if reason else []
        params.append(pytest.param(c, id=c.id, marks=marks))
    return params


def load_cases_from_csv(mode_stem: str) -> list[Case]:
    """Load a mode CSV, expanding `any` rows into the three concrete SoC states."""
    cases: list[Case] = []
    with (CSV_DIR / f"{mode_stem}.csv").open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            soc = row["soc"].strip()
            base = dict(
                mode=row["mode"],
                num=int(row["case"]),
                p1=int(row["input_w"]),
                pv=int(row["pv_w"]),
                discharging=int(row["battery_discharging_w"]),
                charging=int(row["battery_charging_w"]),
                device_to_grid=int(row["device_to_grid_w"]),
                notes=row["notes"],
            )
            if soc == "any":
                for s in SOC_ALL:
                    cases.append(Case(soc=s, any_row=True, **base))
            else:
                cases.append(Case(soc=soc, **base))
    return cases

"""Headless test harness for the Zendure integration.

homeassistant / bleak / paho are NOT installed in this environment and the
manager code is import-coupled to them. To exercise the *real*
``ZendureManager`` power-distribution logic without installing Home Assistant,
we fabricate lightweight stub modules for the missing namespaces so the import
graph resolves. The stubs only need to make imports and class definitions
succeed — the tests never rely on their runtime behaviour (they drive the real
manager against a fake device, see manager_modes/harness.py).
"""

from __future__ import annotations

import sys
import types
from importlib.abc import Loader, MetaPathFinder
from importlib.machinery import ModuleSpec
from pathlib import Path

# --- make the repo root importable (custom_components.zendure_ha.*) ----------
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


# --- universal stub type -----------------------------------------------------
class _AnyMeta(type):
    """Metaclass so stub classes are subscriptable/attr-accessible during import."""

    def __getattr__(cls, name):
        # e.g. NumberMode.SLIDER, Platform.SENSOR — hand back a stub value.
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        return _Any

    def __getitem__(cls, _item):
        return cls  # DataUpdateCoordinator[None], ConfigEntry[X], ...

    def __or__(cls, _o):
        return cls

    def __ror__(cls, _o):
        return cls


class _Any(metaclass=_AnyMeta):
    """Subclassable, callable stand-in for any Home Assistant symbol.

    Deliberately has NO instance ``__getattr__`` fallback: a ``ZendureManager``
    built via ``object.__new__`` inherits from this, and we *want* a real
    ``AttributeError`` if a test forgets to set a needed attribute, rather than
    silently masking it.
    """

    def __init__(self, *args, **kwargs):
        pass

    def __call__(self, *args, **kwargs):
        return self


class _StubModule(types.ModuleType):
    def __getattr__(self, name):
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        obj = type(name, (_Any,), {})  # distinct subclassable type per symbol
        setattr(self, name, obj)
        return obj


class _StubFinder(MetaPathFinder, Loader):
    def __init__(self, roots):
        self._roots = tuple(roots)

    def find_spec(self, fullname, path, target=None):
        if fullname.split(".")[0] in self._roots:
            return ModuleSpec(fullname, self)
        return None

    def create_module(self, spec):
        mod = _StubModule(spec.name)
        mod.__path__ = []  # treat every stub as a package
        return mod

    def exec_module(self, module):
        pass


def _install_stubs():
    """Stub only the namespaces that are genuinely absent, leave real ones alone."""
    probes = {
        "homeassistant": "homeassistant.core",
        "bleak": "bleak",
        "paho": "paho.mqtt.client",
        "aiohttp": "aiohttp",
    }
    missing = []
    for root, probe in probes.items():
        try:
            __import__(probe)
        except Exception:  # noqa: BLE001 - any import failure => stub it
            missing.append(root)
    if missing:
        sys.meta_path.insert(0, _StubFinder(missing))


_install_stubs()


# ---------------------------------------------------------------------------
# MagicMock-based helpers (ported from the earlier suite). These complement the
# plant-model harness in manager_modes/harness.py: instead of driving the system
# to steady state, they build a mock manager + devices and assert on the
# power_discharge / power_charge CALLS the real manager makes. Used by
# test_socfull_bypass.py, test_manager_manual_mode.py, manager_modes/test_soc_boundaries.py.
# ---------------------------------------------------------------------------
import asyncio  # noqa: E402
from datetime import datetime  # noqa: E402
from functools import partial  # noqa: E402
from unittest.mock import AsyncMock, MagicMock  # noqa: E402


def _run(coro):
    """Run a coroutine synchronously (no pytest-asyncio required)."""
    return asyncio.run(coro)


def _sensor(value: int = 0) -> MagicMock:
    """Create a mock sensor with asInt and asNumber attributes."""
    s = MagicMock()
    s.asInt = value
    s.asNumber = float(value)
    return s


def _device(
    *,
    name: str = "dev",
    state=None,
    exports_bypass: bool = True,
    homeOutput: int = 0,
    homeInput: int = 0,
    batteryInput: int = 0,
    batteryOutput: int = 0,
    pwr_offgrid: int = 0,
    electricLevel: int = 50,
    pwr_max: int = 1200,
    bypass: int = 0,
) -> MagicMock:
    """Return a mock ZendureDevice with the given power readings."""
    if state is None:
        from custom_components.zendure_ha.const import DeviceState
        state = DeviceState.INACTIVE

    d = MagicMock()
    d.name = name
    d.state = state
    d.exports_bypass = exports_bypass
    d.homeOutput = _sensor(homeOutput)
    d.homeInput = _sensor(homeInput)
    d.batteryInput = _sensor(batteryInput)
    d.batteryOutput = _sensor(batteryOutput)
    d.electricLevel = _sensor(electricLevel)
    d.byPass = _sensor(bypass)
    d.pwr_offgrid = pwr_offgrid
    d.pwr_produced = 0
    d.pwr_max = pwr_max
    d.kWh = 10.0  # current manager computes globalSoc from d.kWh
    d.charge_optimal = pwr_max // 4
    d.charge_start = pwr_max // 10
    d.discharge_optimal = pwr_max // 4
    d.discharge_start = pwr_max // 10
    d.actualKwh = 10.0
    d.fuseGrp = MagicMock()
    d.fuseGrp.charge_limit.return_value = -pwr_max
    d.fuseGrp.discharge_limit.return_value = pwr_max
    d.power_get = AsyncMock(return_value=True)
    d.power_charge = AsyncMock(side_effect=lambda p, /: p)
    d.power_discharge = AsyncMock(side_effect=lambda p, /: p)
    d.minOutputPower = None  # no min output entity → minOutput returns 0
    d.minOutput = 0
    return d


def _manager(operation=None, devices: list | None = None) -> MagicMock:
    """Return a mock ZendureManager with the minimal state powerChanged() needs."""
    if operation is None:
        from custom_components.zendure_ha.const import ManagerMode
        operation = ManagerMode.STORE_SOLAR

    mgr = MagicMock()
    mgr.devices = devices or []
    mgr.charge = []
    mgr.charge_limit = 0
    mgr.charge_optimal = 0
    mgr.charge_weight = 0
    mgr.charge_time = datetime.min
    mgr.charge_last = datetime.min
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
    mgr.pwr_low = 0
    mgr.operation = operation
    mgr.power = MagicMock()
    mgr.availableKwh = MagicMock()
    mgr.operationstate = MagicMock()
    mgr.manualpower = MagicMock()
    mgr.manualpower.asNumber = 0
    from custom_components.zendure_ha.manager import ZendureManager
    mgr.power_charge = AsyncMock(wraps=partial(ZendureManager.power_charge, mgr))
    mgr.power_discharge = AsyncMock(wraps=partial(ZendureManager.power_discharge, mgr))
    return mgr

# Zendure Manager Mode Tests — Design Spec

**Date:** 2026-06-05
**Source spec:** `docs/manager-mode-power-mappings.md`

## Goal

Comprehensive end-to-end tests for all 7 `ManagerMode` settings, verifying that a given set of (P1, PV, SoC state, device power state) produces the expected device output power. Each mode gets its own test file under `tests/manager_modes/`.

## File Structure

```
tests/
├── conftest.py                              # shared HA stubs + factory helpers (_device, _manager, _sensor, _run)
├── test_socfull_bypass.py                   # existing bypass regression tests (10 cases)
└── manager_modes/
    ├── __init__.py
    ├── test_off.py                          # OFF mode
    ├── test_manual.py                       # MANUAL mode
    ├── test_matching.py                     # MATCHING mode
    ├── test_matching_discharge.py           # MATCHING_DISCHARGE mode
    ├── test_matching_charge.py              # MATCHING_CHARGE mode
    └── test_store_solar.py                  # STORE_SOLAR mode
```

## Test Architecture

### Two classes per mode file

Each mode file contains two test classes:

1. **`Test<Mode>SingleDevice`** — parametrized spec rows from `manager-mode-power-mappings.md`. One device in the system. Each row maps to a `pytest.param` with a descriptive `id`.

2. **`Test<Mode>MultiDevice`** — 8 additional scenarios with 2 devices sharing a fuse group, testing weighted distribution, fuse limits, and mixed-state behavior.

### Test approach: end-to-end `powerChanged`

All tests call `ZendureManager.powerChanged(mgr, p1, isFast, time)` directly and verify the resulting `d.power_discharge(pwr)` / `d.power_charge(pwr)` calls on each mock device. This exercises:

- Device classification (charge/discharge/idle lists)
- Mode dispatch
- Power distribution (weighted by SoC, capped by fuse limits)
- SOCFULL solar passthrough
- SOCEMPTY exclusion
- Bypass correction

### Spec row → mock sensor mapping

Each spec row column translates to mock device attributes:

| Spec column | Mock sensor(s) |
|:---|:---|
| PV | `homeOutput.asInt` (solar flows through home output) |
| Discharging | `batteryOutput.asInt`, `homeOutput.asInt` > 0 |
| Charging | `batteryInput.asInt`, `homeInput.asInt` > 0 |
| SoC FULL | `state = SOCFULL`, `electricLevel = 100` |
| SoC EMPTY | `state = SOCEMPTY`, `electricLevel = 0` |
| SoC not full | `state = INACTIVE`, `electricLevel = 50` |
| Manual Power | `manualpower.asNumber` on manager |

## Modes

### OFF (mode 0)
- **Single-device:** 1 case — any P1/PV/SoC → 0W (all devices off via `power_off()`)
- **Multi-device:** 1 case — 2 devices, both off

### MANUAL (mode 1)
- **Single-device:** 25 cases covering:
  - Positive manual power (+300W): PV 0/50/200/500W × SoC not full/FULL/EMPTY
  - Zero manual power (0W): PV 0/200W × SoC not full/FULL/EMPTY
  - Negative manual power (−300W): PV 0/200/500W × SoC not full/FULL/EMPTY
- **Multi-device:** 8 cases (same fuse group)

### MATCHING (mode 2)
- **Single-device:** 25 cases covering:
  - Positive P1 (100W, 300W, 500W): PV 0/50/100/200W × SoC not full/FULL/EMPTY
  - Zero P1 (0W): PV 0/200W × SoC not full/FULL
  - Negative P1 (−100W, −300W): PV 0/100/200/500W × SoC not full/FULL
- **Multi-device:** 8 cases

### MATCHING_DISCHARGE (mode 3)
- **Single-device:** 22 cases — same P1/PV combos as MATCHING but negative P1 always clamped to 0
- **Multi-device:** 8 cases

### MATCHING_CHARGE (mode 4)
- **Single-device:** 23 cases — battery never discharges; only solar passes through
- **Multi-device:** 8 cases

### STORE_SOLAR (mode 5)
- **Single-device:** 20 cases — all solar stored in battery; only FULL bypass can send solar to home
- **Multi-device:** 8 cases

## Multi-Device Scenarios (per mode)

| # | Devices | What it tests |
|:--|:---|:---|
| 1 | Same SoC, same PV | equal weighted split |
| 2 | Full + Empty | full=0W, empty=all |
| 3 | Full + Not Full | full solar-only, not-full gets remainder |
| 4 | One with PV, one without | solar device carries more load |
| 5 | Total demand > fuse limit | power capped at fuse group max |
| 6 | Mixed charge + discharge | stop-loop preserves bypass device |
| 7 | Both FULL, different PV | each capped at own solar |
| 8 | Empty + Not Full | empty skipped, not-full gets all |

## Shared Helpers

### In `tests/conftest.py` (already exists)
- `_run(coro)` — synchronous coroutine runner
- `_sensor(value)` — mock sensor with `asInt`/`asNumber`
- `_device(**kwargs)` — mock device with power sensors
- `_manager(operation, devices)` — mock manager with accumulators

### New helper: `_spec_to_mgr(spec_row, operation, devices)`
Translates a spec row tuple `(p1, pv, soc_state, discharging, charging, expected_output)` into a configured manager with mock devices whose sensor values produce the correct classification. Returns `(mgr, devices_dict)` for test assertions.

## Verification

```bash
pytest tests/manager_modes/ -v
```

Expected: all parametrized cases pass with descriptive IDs visible in output.

## Non-Goals

- Testing MQTT communication or real device I/O
- Testing entity creation or HA platform registration
- Testing `Api.py`, `config_flow.py`, or `migration.py`
- Performance/stress testing

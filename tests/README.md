# Tests

Behavioural tests for the Zendure Home Assistant integration — primarily the
`ZendureManager` power-distribution logic across every `ManagerMode`.

## No Home Assistant install required

`homeassistant`, `bleak` and `paho` are **not** needed. `tests/conftest.py`
installs lightweight stub modules (via a `sys.meta_path` finder) so the **real**
`custom_components.zendure_ha.manager` imports and runs headless. Just:

```bash
pip install pytest        # the only dependency
```

## Running the tests

Run everything from the **repo root** (`tests/conftest.py` puts the repo on
`sys.path` automatically).

```bash
# All tests
python3 -m pytest tests/ -q

# Only the manager-mode suite (the CSV-driven conformance tests)
python3 -m pytest tests/manager_modes -q

# A single component / mode file
python3 -m pytest tests/manager_modes/test_matching.py -q
python3 -m pytest tests/test_socfull_bypass.py -q

# A single parametrized case, by id (list the exact ids with -v or --co -q first)
python3 -m pytest "tests/manager_modes/test_matching.py::test_matching_matches_spec[MATCHING-r108-p1=300-pv=200-not full]"

# Filter by keyword — matches test ids (note: `=` cannot be used in a -k expression)
python3 -m pytest tests/ -k "matching_charge"
python3 -m pytest tests/ -k "socfull"

# Verbose list of every case
python3 -m pytest tests/manager_modes -v

# Stop on first failure, with full traceback
python3 -m pytest tests/ -x -vv

# Show xfail / xpass reasons
python3 -m pytest tests/manager_modes -rxX
```

Inside a Claude Code session you can run any of these by prefixing with `!`,
e.g. `! python3 -m pytest tests/ -q`.

## Layout

| Path | Tests | What it covers |
|---|---:|---|
| `manager_modes/test_matching.py` | 144 | MATCHING mode — CSV-driven conformance |
| `manager_modes/test_matching_discharge.py` | 84 | MATCHING_DISCHARGE — CSV-driven |
| `manager_modes/test_matching_charge.py` | 108 | MATCHING_CHARGE — CSV-driven |
| `manager_modes/test_store_solar.py` | 90 | STORE_SOLAR — CSV-driven |
| `manager_modes/test_manual.py` | 84 | MANUAL — CSV-driven |
| `manager_modes/test_off.py` | 9 | OFF — no distribution, state = OFF |
| `manager_modes/test_smoke_import.py` | 1 | the real manager imports through the stubs |
| `manager_modes/test_soc_boundaries.py` | 8 | socSet / minSoc thresholds (mock-based) |
| `test_manager_manual_mode.py` | 11 | MANUAL dispatch + SOCFULL passthrough (mock-based) |
| `test_socfull_bypass.py` | 10 | SOCFULL solar-bypass setpoint / stop-loop (mock-based) |
| `test_entity_recovery.py` | 14 | entity restore / ACE 1500 startup regressions |
| `conftest.py` | — | HA stubs + shared `_device` / `_manager` / `_sensor` helpers |
| `manager_modes/harness.py` | — | plant-model harness (`drive_metered`, `FakeDevice`) |
| `manager_modes/*.csv` | — | per-mode spec data (source of truth) |

## Two testing styles

1. **CSV-driven conformance** (`manager_modes/test_<mode>.py` + `harness.py`).
   Each row of `manager_modes/<mode>.csv` is a case. The real `powerChanged` is
   driven through a **residual P1 meter** (a Shelly-3EM-style grid meter,
   `p1 = load − net`) and a physical battery plant until steady state, then the
   result is asserted against the row (`Device to grid` / `Battery Discharging` /
   `Battery Charging`). `any` SoC rows expand to EMPTY / FULL / not-full.

2. **Command-assertion** (`test_socfull_bypass.py`, `test_manager_manual_mode.py`,
   `manager_modes/test_soc_boundaries.py`). Build a mock manager + devices with
   the `conftest.py` helpers and assert on the `power_discharge` / `power_charge`
   **calls** the manager makes.

## Source of truth

`docs/manager-mode-power-mappings.md` and `tests/manager_modes/*.csv` are kept
**cell-for-cell identical** (verified in CI-style checks). Both are validated
against a physical oracle (power balance `G = PV + D − C`, no simultaneous
charge/discharge, no AC-grid charge in automatic modes, FULL = solar bypass,
etc.). Edit the spec, keep the CSV in sync, and the tests verify the code matches.

## Known-failing tests

The mock-based `test_entity_recovery.py`, `test_socfull_bypass.py`
(`TestPowerChargeStopLoop`), `test_manager_manual_mode.py`
(`TestManualModeWithSocfull`) and two `test_soc_boundaries.py` cases currently
fail. These are **pre-existing** and unrelated to the CSV data — they fail on the
untouched base revision too (harness/behaviour gaps, and the ACE1500 / restore
regressions that `test_entity_recovery.py` documents). The CSV-driven mode suites
are all green.

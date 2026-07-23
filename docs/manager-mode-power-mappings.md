# Zendure Manager Mode — Power Mapping Tables

Behaviour of the Zendure Home Assistant integration's power distribution across all `ManagerMode` settings.
Each table shows how a single device behaves given the mode, P1 meter reading, solar input (PV), and battery state of charge (SoC).

TODO: add the 2nd and more devices (due to different SoC)

**SoC states** (from `DeviceState` enum):

| # | Label | DeviceState | Meaning |
|:---:|:---:|:---:|:---:|
| 1 | not full | ACTIVE / INACTIVE | battery can charge and discharge |
| 2 | FULL | SOCFULL | battery full, bypass may pass solar to home |
| 3 | EMPTY | SOCEMPTY | battery can't discharge, can still charge or pass solar |
| 4 | any | — | result is the same regardless of SoC |

**Columns:**

| # | Column | Description |
|:---:|:---:|:---:|
| 1 | Battery Discharging | battery output to home |
| 2 | Battery Charging | grid/solar into battery |
| 3 | Device to grid | net power from device to home bus; negative = drawing from grid |
| 4 | P1 | Power meter. Ignored in MANUAL mode. Negative value means that other devices already export to grid |

---

## AC grid charging (global spec rule)

No device charges its battery **from the AC grid** in any automatic mode. MATCHING, MATCHING_DISCHARGE, MATCHING_CHARGE and STORE_SOLAR only ever charge the battery from the device's **own solar**. Consequently every `Device to grid` value in those tables is **≥ 0** — a battery is never filled by importing from the grid.

Only **MANUAL** mode may import from the grid: a negative *Manual Power* asks the device to draw and store grid energy (a negative `Device to grid`). This works **only on devices that physically support AC input** (e.g. Hyper2000). Devices of the HUB family (Hub1200 / Hub2000) have no AC-charge path — they ignore a negative setpoint and stay idle, so their battery still only ever charges from available solar. **The negative-power rows in the MANUAL table below assume an AC-capable device.**

---

## Notes for test generation

These tables are the source of truth for the tests. When turning rows into cases:

1. **Expand `any` rows into three cases.** A row with `SoC State = any` asserts the result is identical for EMPTY, FULL and not full. Materialise it as three separate test cases (one per SoC state) so a test actually proves the collapse holds, rather than trusting it.

2. **Negative MANUAL power depends on the device.** The negative *Manual Power* rows (grid import) assume an **AC-capable device** (e.g. Hyper2000) — run them only against such a device. A **HUB-family device (Hub1200 / Hub2000)** has no AC-charge path, so for a HUB a negative setpoint behaves like **STORE_SOLAR**: it charges only from its own solar (FULL bypasses to home), never from the grid. Concretely, for a HUB:
   - MANUAL −100 W / 0 W PV → `0 / 0 / 0` (idle, nothing to charge from)
   - MANUAL −100 W / 200 W PV, not full or EMPTY → `0 / 200 / 0` (store solar, `Device to grid = 0`)
   - MANUAL −100 W / 200 W PV, FULL → `0 / 0 / 200` (bypass solar to home)

---

## OFF Mode

**Test data:** [`tests/manager_modes/off.csv`](../tests/manager_modes/off.csv)

`power_off()` — the device is **not managed** by Zendure Manager; all devices are explicitly powered off and no power distribution occurs. `operationstate` set to OFF regardless of P1, PV, or SoC inputs.

| # | P1 | PV | SoC State | Battery Discharging | Battery Charging | Device to grid | Notes |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 1 | any | any | any | 0 W | 0 W | 0 W | device not managed by Zendure Manager (powered off) |

## MANUAL Mode — Power Mappings

**Test data:** [`tests/manager_modes/manual.csv`](../tests/manager_modes/manual.csv)

`manualpower` — device outputs (positive) or draws (negative) exactly the set manual power value. P1 meter is ignored. PV and battery contribute at hardware level but the manager commands only the manual power. FULL bypass may override the setpoint (output caps at PV). SOCEMPTY cannot discharge the battery, but any PV **surplus above the output setpoint still charges it** — exactly like a not-full battery (while the battery is not full there is nowhere else for the surplus to go). Negative manual power imports from the AC grid **only on devices that support AC input** (e.g. Hyper2000); HUB-family devices (Hub1200 / Hub2000) ignore it and idle, so their battery only ever charges from solar.

| # | Manual Power | PV | SoC State | Battery Discharging | Battery Charging | Device to grid | Notes |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 1 | -300 W | 0 W | EMPTY | 0 W | 300 W | -300 W | full grid charging |
| 2 | -300 W | 0 W | FULL | 0 W | 0 W | 0 W | can't charge a full battery |
| 3 | -300 W | 0 W | not full | 0 W | 300 W | -300 W | full grid charging |
| 4 | -300 W | 50 W | EMPTY | 0 W | 350 W | -300 W | grid charge 300 W + 50 W solar into battery |
| 5 | -300 W | 50 W | FULL | 0 W | 0 W | 50 W | battery full: bypass all solar to home |
| 6 | -300 W | 50 W | not full | 0 W | 350 W | -300 W | grid charge 300 W + 50 W solar into battery |
| 7 | -300 W | 200 W | EMPTY | 0 W | 500 W | -300 W | 300 W from grid + 200 W solar into battery; net grid draw 300 W |
| 8 | -300 W | 200 W | FULL | 0 W | 0 W | 200 W | battery full, can't charge; bypass sends all solar to home |
| 9 | -300 W | 200 W | not full | 0 W | 500 W | -300 W | 300 W from grid + 200 W solar into battery; net grid draw 300 W |
| 10 | -300 W | 500 W | EMPTY | 0 W | 800 W | -300 W | 300 W from grid + 500 W solar into battery; net grid draw 300 W |
| 11 | -300 W | 500 W | FULL | 0 W | 0 W | 500 W | battery full, can't charge; bypass sends all solar to home |
| 12 | -300 W | 500 W | not full | 0 W | 800 W | -300 W | 300 W from grid + 500 W solar into battery; net grid draw 300 W |
| 13 | -100 W | 0 W | EMPTY | 0 W | 100 W | -100 W | full grid charging |
| 14 | -100 W | 0 W | FULL | 0 W | 0 W | 0 W | can't charge a full battery |
| 15 | -100 W | 0 W | not full | 0 W | 100 W | -100 W | full grid charging |
| 16 | -100 W | 50 W | EMPTY | 0 W | 150 W | -100 W | grid charge 100 W + 50 W solar into battery |
| 17 | -100 W | 50 W | FULL | 0 W | 0 W | 50 W | battery full: bypass all solar to home |
| 18 | -100 W | 50 W | not full | 0 W | 150 W | -100 W | grid charge 100 W + 50 W solar into battery |
| 19 | -100 W | 200 W | EMPTY | 0 W | 300 W | -100 W | 100 W from grid + 200 W solar into battery; net grid draw 100 W |
| 20 | -100 W | 200 W | FULL | 0 W | 0 W | 200 W | battery full, can't charge; bypass sends all solar to home |
| 21 | -100 W | 200 W | not full | 0 W | 300 W | -100 W | 100 W from grid + 200 W solar into battery; net grid draw 100 W |
| 22 | -100 W | 500 W | EMPTY | 0 W | 600 W | -100 W | grid charge 100 W + 500 W solar into battery |
| 23 | -100 W | 500 W | FULL | 0 W | 0 W | 500 W | battery full: bypass all solar to home |
| 24 | -100 W | 500 W | not full | 0 W | 600 W | -100 W | grid charge 100 W + 500 W solar into battery |
| 25 | -50 W | 0 W | EMPTY | 0 W | 50 W | -50 W | full grid charging |
| 26 | -50 W | 0 W | FULL | 0 W | 0 W | 0 W | can't charge a full battery |
| 27 | -50 W | 0 W | not full | 0 W | 50 W | -50 W | full grid charging |
| 28 | -50 W | 50 W | EMPTY | 0 W | 100 W | -50 W | grid charge 50 W + 50 W solar into battery |
| 29 | -50 W | 50 W | FULL | 0 W | 0 W | 50 W | battery full: bypass all solar to home |
| 30 | -50 W | 50 W | not full | 0 W | 100 W | -50 W | grid charge 50 W + 50 W solar into battery |
| 31 | -50 W | 200 W | EMPTY | 0 W | 250 W | -50 W | 50 W from grid + 200 W solar into battery; net grid draw 50 W |
| 32 | -50 W | 200 W | FULL | 0 W | 0 W | 200 W | battery full, can't charge; bypass sends all solar to home |
| 33 | -50 W | 200 W | not full | 0 W | 250 W | -50 W | 50 W from grid + 200 W solar into battery; net grid draw 50 W |
| 34 | -50 W | 500 W | EMPTY | 0 W | 550 W | -50 W | grid charge 50 W + 500 W solar into battery |
| 35 | -50 W | 500 W | FULL | 0 W | 0 W | 500 W | battery full: bypass all solar to home |
| 36 | -50 W | 500 W | not full | 0 W | 550 W | -50 W | grid charge 50 W + 500 W solar into battery |
| 37 | 0 W | 0 W | any | 0 W | 0 W | 0 W | idle, nothing to do |
| 38 | 0 W | 50 W | EMPTY | 0 W | 50 W | 0 W | all solar stored in battery |
| 39 | 0 W | 50 W | FULL | 0 W | 0 W | 50 W | battery full: bypass all solar to home |
| 40 | 0 W | 50 W | not full | 0 W | 50 W | 0 W | all solar stored in battery |
| 41 | 0 W | 200 W | EMPTY | 0 W | 200 W | 0 W | solar charges empty battery |
| 42 | 0 W | 200 W | FULL | 0 W | 0 W | 200 W | FULL battery bypasses solar to home |
| 43 | 0 W | 200 W | not full | 0 W | 200 W | 0 W | solar charges battery |
| 44 | 0 W | 500 W | EMPTY | 0 W | 500 W | 0 W | all solar stored in battery |
| 45 | 0 W | 500 W | FULL | 0 W | 0 W | 500 W | battery full: bypass all solar to home |
| 46 | 0 W | 500 W | not full | 0 W | 500 W | 0 W | all solar stored in battery |
| 47 | 50 W | 0 W | EMPTY | 0 W | 0 W | 0 W | can't discharge, no solar |
| 48 | 50 W | 0 W | FULL | 0 W | 0 W | 0 W | nothing to bypass |
| 49 | 50 W | 0 W | not full | 50 W | 0 W | 50 W | pure battery discharge |
| 50 | 50 W | 50 W | any | 0 W | 0 W | 50 W | solar passes to home, battery idle |
| 51 | 50 W | 200 W | EMPTY | 0 W | 150 W | 50 W | can't discharge; solar covers 50 W output, 150 W excess charges battery |
| 52 | 50 W | 200 W | FULL | 0 W | 0 W | 200 W | bypass overrides, all solar to home |
| 53 | 50 W | 200 W | not full | 0 W | 150 W | 50 W | solar covers all output, 150 W excess charges battery |
| 54 | 50 W | 500 W | EMPTY | 0 W | 450 W | 50 W | surplus solar charges battery |
| 55 | 50 W | 500 W | FULL | 0 W | 0 W | 500 W | battery full: bypass all solar to home |
| 56 | 50 W | 500 W | not full | 0 W | 450 W | 50 W | surplus solar charges battery |
| 57 | 100 W | 0 W | EMPTY | 0 W | 0 W | 0 W | can't discharge, no solar |
| 58 | 100 W | 0 W | FULL | 0 W | 0 W | 0 W | nothing to bypass |
| 59 | 100 W | 0 W | not full | 100 W | 0 W | 100 W | pure battery discharge |
| 60 | 100 W | 50 W | EMPTY | 0 W | 0 W | 50 W | can't discharge, solar only |
| 61 | 100 W | 50 W | FULL | 0 W | 0 W | 50 W | bypass only |
| 62 | 100 W | 50 W | not full | 50 W | 0 W | 100 W | 50W solar + 50W battery |
| 63 | 100 W | 200 W | EMPTY | 0 W | 100 W | 100 W | can't discharge; solar covers 100 W output, 100 W excess charges battery |
| 64 | 100 W | 200 W | FULL | 0 W | 0 W | 200 W | bypass overrides, all solar to home |
| 65 | 100 W | 200 W | not full | 0 W | 100 W | 100 W | solar covers all output, 100 W excess charges battery |
| 66 | 100 W | 500 W | EMPTY | 0 W | 400 W | 100 W | surplus solar charges battery |
| 67 | 100 W | 500 W | FULL | 0 W | 0 W | 500 W | battery full: bypass all solar to home |
| 68 | 100 W | 500 W | not full | 0 W | 400 W | 100 W | surplus solar charges battery |
| 69 | 300 W | 0 W | EMPTY | 0 W | 0 W | 0 W | can't discharge, no solar |
| 70 | 300 W | 0 W | FULL | 0 W | 0 W | 0 W | nothing to bypass |
| 71 | 300 W | 0 W | not full | 300 W | 0 W | 300 W | pure battery discharge |
| 72 | 300 W | 50 W | EMPTY | 0 W | 0 W | 50 W | can't discharge, solar only |
| 73 | 300 W | 50 W | FULL | 0 W | 0 W | 50 W | bypass only |
| 74 | 300 W | 50 W | not full | 250 W | 0 W | 300 W | mostly battery discharge |
| 75 | 300 W | 200 W | EMPTY | 0 W | 0 W | 200 W | can't discharge, solar passes to home |
| 76 | 300 W | 200 W | FULL | 0 W | 0 W | 200 W | bypass caps output at PV |
| 77 | 300 W | 200 W | not full | 100 W | 0 W | 300 W | solar covers 200 W, battery covers 100 W |
| 78 | 300 W | 500 W | EMPTY | 0 W | 200 W | 300 W | can't discharge; solar covers 300 W output, 200 W excess charges battery |
| 79 | 300 W | 500 W | FULL | 0 W | 0 W | 500 W | bypass overrides manual setpoint |
| 80 | 300 W | 500 W | not full | 0 W | 200 W | 300 W | solar covers all output, 200 W excess charges battery |

## MATCHING Mode — Power Mappings

**Test data:** [`tests/manager_modes/matching.csv`](../tests/manager_modes/matching.csv)

`setpoint = P1 ± device contributions` → `power_discharge` (setpoint ≥ 0) or `power_charge` (setpoint < 0) — balances P1 to zero using available PV and battery. P1 > 0: discharges to cover house demand, PV excess charges battery. P1 < 0: charges battery from own available solar only (never from grid — no device can force AC grid charging in this mode); if the export comes from another device it stays unmatched. P1 = 0: all solar charges battery. FULL battery bypasses all solar to home. SOCEMPTY limits output to solar only.

| # | P1 | PV | SoC State | Battery Discharging | Battery Charging | Device to grid | Notes |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 1 | -300 W | 0 W | any | 0 W | 0 W | 0 W | idle, nothing to do |
| 2 | -300 W | 50 W | EMPTY | 0 W | 50 W | 0 W | all solar stored in battery |
| 3 | -300 W | 50 W | FULL | 0 W | 0 W | 50 W | battery full: bypass all solar to home |
| 4 | -300 W | 50 W | not full | 0 W | 50 W | 0 W | all solar stored in battery |
| 5 | -300 W | 100 W | EMPTY | 0 W | 100 W | 0 W | all solar stored in battery |
| 6 | -300 W | 100 W | FULL | 0 W | 0 W | 100 W | battery full: bypass all solar to home |
| 7 | -300 W | 100 W | not full | 0 W | 100 W | 0 W | all solar stored in battery |
| 8 | -300 W | 200 W | EMPTY | 0 W | 200 W | 0 W | all solar stored in battery |
| 9 | -300 W | 200 W | FULL | 0 W | 0 W | 200 W | battery full: bypass all solar to home |
| 10 | -300 W | 200 W | not full | 0 W | 200 W | 0 W | all solar stored in battery |
| 11 | -300 W | 300 W | EMPTY | 0 W | 300 W | 0 W | all solar stored in battery |
| 12 | -300 W | 300 W | FULL | 0 W | 0 W | 300 W | battery full: bypass all solar to home |
| 13 | -300 W | 300 W | not full | 0 W | 300 W | 0 W | all solar stored in battery |
| 14 | -300 W | 500 W | EMPTY | 0 W | 500 W | 0 W | store all available solar; can't charge from grid |
| 15 | -300 W | 500 W | FULL | 0 W | 0 W | 500 W | bypass overrides, solar to home |
| 16 | -300 W | 500 W | not full | 0 W | 500 W | 0 W | store all available solar; can't charge from grid |
| 17 | -100 W | 0 W | any | 0 W | 0 W | 0 W | idle, nothing to do |
| 18 | -100 W | 50 W | EMPTY | 0 W | 50 W | 0 W | all solar stored in battery |
| 19 | -100 W | 50 W | FULL | 0 W | 0 W | 50 W | battery full: bypass all solar to home |
| 20 | -100 W | 50 W | not full | 0 W | 50 W | 0 W | all solar stored in battery |
| 21 | -100 W | 100 W | EMPTY | 0 W | 100 W | 0 W | solar stored in battery |
| 22 | -100 W | 100 W | FULL | 0 W | 0 W | 100 W | bypass sends solar to home |
| 23 | -100 W | 100 W | not full | 0 W | 100 W | 0 W | solar stored in battery |
| 24 | -100 W | 200 W | EMPTY | 0 W | 200 W | 0 W | store all available solar; can't charge from grid |
| 25 | -100 W | 200 W | FULL | 0 W | 0 W | 200 W | bypass all solar to home |
| 26 | -100 W | 200 W | not full | 0 W | 200 W | 0 W | store all available solar; can't charge from grid |
| 27 | -100 W | 300 W | EMPTY | 0 W | 300 W | 0 W | all solar stored in battery |
| 28 | -100 W | 300 W | FULL | 0 W | 0 W | 300 W | battery full: bypass all solar to home |
| 29 | -100 W | 300 W | not full | 0 W | 300 W | 0 W | all solar stored in battery |
| 30 | -100 W | 500 W | EMPTY | 0 W | 500 W | 0 W | all solar stored in battery |
| 31 | -100 W | 500 W | FULL | 0 W | 0 W | 500 W | battery full: bypass all solar to home |
| 32 | -100 W | 500 W | not full | 0 W | 500 W | 0 W | all solar stored in battery |
| 33 | 0 W | 0 W | any | 0 W | 0 W | 0 W | idle, nothing to do |
| 34 | 0 W | 50 W | EMPTY | 0 W | 50 W | 0 W | all solar stored in battery |
| 35 | 0 W | 50 W | FULL | 0 W | 0 W | 50 W | battery full: bypass all solar to home |
| 36 | 0 W | 50 W | not full | 0 W | 50 W | 0 W | all solar stored in battery |
| 37 | 0 W | 100 W | EMPTY | 0 W | 100 W | 0 W | all solar stored in battery |
| 38 | 0 W | 100 W | FULL | 0 W | 0 W | 100 W | battery full: bypass all solar to home |
| 39 | 0 W | 100 W | not full | 0 W | 100 W | 0 W | all solar stored in battery |
| 40 | 0 W | 200 W | EMPTY | 0 W | 200 W | 0 W | all solar stored in battery |
| 41 | 0 W | 200 W | FULL | 0 W | 0 W | 200 W | bypass passes solar to home |
| 42 | 0 W | 200 W | not full | 0 W | 200 W | 0 W | all solar stored in battery |
| 43 | 0 W | 300 W | EMPTY | 0 W | 300 W | 0 W | all solar stored in battery |
| 44 | 0 W | 300 W | FULL | 0 W | 0 W | 300 W | battery full: bypass all solar to home |
| 45 | 0 W | 300 W | not full | 0 W | 300 W | 0 W | all solar stored in battery |
| 46 | 0 W | 500 W | EMPTY | 0 W | 500 W | 0 W | all solar stored in battery |
| 47 | 0 W | 500 W | FULL | 0 W | 0 W | 500 W | battery full: bypass all solar to home |
| 48 | 0 W | 500 W | not full | 0 W | 500 W | 0 W | all solar stored in battery |
| 49 | 50 W | 0 W | EMPTY | 0 W | 0 W | 0 W | can't discharge, P1 unmatched |
| 50 | 50 W | 0 W | FULL | 0 W | 0 W | 0 W | nothing to give |
| 51 | 50 W | 0 W | not full | 50 W | 0 W | 50 W | pure battery discharge |
| 52 | 50 W | 50 W | any | 0 W | 0 W | 50 W | solar passes to home, battery idle |
| 53 | 50 W | 100 W | EMPTY | 0 W | 50 W | 50 W | surplus solar charges battery |
| 54 | 50 W | 100 W | FULL | 0 W | 0 W | 100 W | battery full: bypass all solar to home |
| 55 | 50 W | 100 W | not full | 0 W | 50 W | 50 W | surplus solar charges battery |
| 56 | 50 W | 200 W | EMPTY | 0 W | 150 W | 50 W | solar covers P1, 150 W excess charges battery |
| 57 | 50 W | 200 W | FULL | 0 W | 0 W | 200 W | bypass sends all solar to home |
| 58 | 50 W | 200 W | not full | 0 W | 150 W | 50 W | PV excess charges battery, matches P1 |
| 59 | 50 W | 300 W | EMPTY | 0 W | 250 W | 50 W | surplus solar charges battery |
| 60 | 50 W | 300 W | FULL | 0 W | 0 W | 300 W | battery full: bypass all solar to home |
| 61 | 50 W | 300 W | not full | 0 W | 250 W | 50 W | surplus solar charges battery |
| 62 | 50 W | 500 W | EMPTY | 0 W | 450 W | 50 W | surplus solar charges battery |
| 63 | 50 W | 500 W | FULL | 0 W | 0 W | 500 W | battery full: bypass all solar to home |
| 64 | 50 W | 500 W | not full | 0 W | 450 W | 50 W | surplus solar charges battery |
| 65 | 100 W | 0 W | EMPTY | 0 W | 0 W | 0 W | can't discharge, P1 unmatched |
| 66 | 100 W | 0 W | FULL | 0 W | 0 W | 0 W | nothing to give |
| 67 | 100 W | 0 W | not full | 100 W | 0 W | 100 W | pure battery discharge |
| 68 | 100 W | 50 W | EMPTY | 0 W | 0 W | 50 W | partial match, solar only |
| 69 | 100 W | 50 W | FULL | 0 W | 0 W | 50 W | bypass only, can't fully match P1 |
| 70 | 100 W | 50 W | not full | 50 W | 0 W | 100 W | 50 W solar + 50 W battery = matches P1 |
| 71 | 100 W | 100 W | any | 0 W | 0 W | 100 W | solar passes to home, battery idle |
| 72 | 100 W | 200 W | EMPTY | 0 W | 100 W | 100 W | solar covers P1, 100 W excess charges battery |
| 73 | 100 W | 200 W | FULL | 0 W | 0 W | 200 W | bypass sends all solar to home |
| 74 | 100 W | 200 W | not full | 0 W | 100 W | 100 W | PV excess charges battery, matches P1 |
| 75 | 100 W | 300 W | EMPTY | 0 W | 200 W | 100 W | solar covers P1, 200 W excess charges battery |
| 76 | 100 W | 300 W | FULL | 0 W | 0 W | 300 W | bypass sends all solar to home |
| 77 | 100 W | 300 W | not full | 0 W | 200 W | 100 W | 200 W PV excess charges battery, matches P1 |
| 78 | 100 W | 500 W | EMPTY | 0 W | 400 W | 100 W | surplus solar charges battery |
| 79 | 100 W | 500 W | FULL | 0 W | 0 W | 500 W | battery full: bypass all solar to home |
| 80 | 100 W | 500 W | not full | 0 W | 400 W | 100 W | surplus solar charges battery |
| 81 | 200 W | 0 W | EMPTY | 0 W | 0 W | 0 W | can't discharge, P1 unmatched |
| 82 | 200 W | 0 W | FULL | 0 W | 0 W | 0 W | nothing to give |
| 83 | 200 W | 0 W | not full | 200 W | 0 W | 200 W | pure battery discharge |
| 84 | 200 W | 50 W | EMPTY | 0 W | 0 W | 50 W | solar passes to home, battery idle |
| 85 | 200 W | 50 W | FULL | 0 W | 0 W | 50 W | battery full: bypass all solar to home |
| 86 | 200 W | 50 W | not full | 150 W | 0 W | 200 W | solar + battery cover demand |
| 87 | 200 W | 100 W | EMPTY | 0 W | 0 W | 100 W | can't discharge, solar only (100 W unmatched) |
| 88 | 200 W | 100 W | FULL | 0 W | 0 W | 100 W | bypass only, partial match |
| 89 | 200 W | 100 W | not full | 100 W | 0 W | 200 W | 100 W solar + 100 W battery = matches P1 |
| 90 | 200 W | 200 W | any | 0 W | 0 W | 200 W | solar passes to home, battery idle |
| 91 | 200 W | 300 W | EMPTY | 0 W | 100 W | 200 W | surplus solar charges battery |
| 92 | 200 W | 300 W | FULL | 0 W | 0 W | 300 W | battery full: bypass all solar to home |
| 93 | 200 W | 300 W | not full | 0 W | 100 W | 200 W | surplus solar charges battery |
| 94 | 200 W | 500 W | EMPTY | 0 W | 300 W | 200 W | surplus solar charges battery |
| 95 | 200 W | 500 W | FULL | 0 W | 0 W | 500 W | battery full: bypass all solar to home |
| 96 | 200 W | 500 W | not full | 0 W | 300 W | 200 W | surplus solar charges battery |
| 97 | 300 W | 0 W | EMPTY | 0 W | 0 W | 0 W | can't discharge, P1 unmatched |
| 98 | 300 W | 0 W | FULL | 0 W | 0 W | 0 W | nothing to give |
| 99 | 300 W | 0 W | not full | 300 W | 0 W | 300 W | high demand, pure battery |
| 100 | 300 W | 50 W | EMPTY | 0 W | 0 W | 50 W | solar passes to home, battery idle |
| 101 | 300 W | 50 W | FULL | 0 W | 0 W | 50 W | battery full: bypass all solar to home |
| 102 | 300 W | 50 W | not full | 250 W | 0 W | 300 W | solar + battery cover demand |
| 103 | 300 W | 100 W | EMPTY | 0 W | 0 W | 100 W | solar passes to home, battery idle |
| 104 | 300 W | 100 W | FULL | 0 W | 0 W | 100 W | battery full: bypass all solar to home |
| 105 | 300 W | 100 W | not full | 200 W | 0 W | 300 W | solar + battery cover demand |
| 106 | 300 W | 200 W | EMPTY | 0 W | 0 W | 200 W | solar passes to home, battery idle |
| 107 | 300 W | 200 W | FULL | 0 W | 0 W | 200 W | battery full: bypass all solar to home |
| 108 | 300 W | 200 W | not full | 100 W | 0 W | 300 W | solar + battery cover demand |
| 109 | 300 W | 300 W | any | 0 W | 0 W | 300 W | solar passes to home, battery idle |
| 110 | 300 W | 500 W | EMPTY | 0 W | 200 W | 300 W | surplus solar charges battery |
| 111 | 300 W | 500 W | FULL | 0 W | 0 W | 500 W | battery full: bypass all solar to home |
| 112 | 300 W | 500 W | not full | 0 W | 200 W | 300 W | surplus solar charges battery |
| 113 | 500 W | 0 W | EMPTY | 0 W | 0 W | 0 W | idle, nothing to do |
| 114 | 500 W | 0 W | FULL | 0 W | 0 W | 0 W | idle, nothing to bypass |
| 115 | 500 W | 0 W | not full | 500 W | 0 W | 500 W | pure battery discharge |
| 116 | 500 W | 50 W | EMPTY | 0 W | 0 W | 50 W | solar passes to home, battery idle |
| 117 | 500 W | 50 W | FULL | 0 W | 0 W | 50 W | battery full: bypass all solar to home |
| 118 | 500 W | 50 W | not full | 450 W | 0 W | 500 W | solar + battery cover demand |
| 119 | 500 W | 100 W | EMPTY | 0 W | 0 W | 100 W | solar passes to home, battery idle |
| 120 | 500 W | 100 W | FULL | 0 W | 0 W | 100 W | battery full: bypass all solar to home |
| 121 | 500 W | 100 W | not full | 400 W | 0 W | 500 W | solar + battery cover demand |
| 122 | 500 W | 200 W | EMPTY | 0 W | 0 W | 200 W | can't discharge, solar only |
| 123 | 500 W | 200 W | FULL | 0 W | 0 W | 200 W | bypass only, can't fully match P1 |
| 124 | 500 W | 200 W | not full | 300 W | 0 W | 500 W | battery + solar combined |
| 125 | 500 W | 300 W | EMPTY | 0 W | 0 W | 300 W | solar passes to home, battery idle |
| 126 | 500 W | 300 W | FULL | 0 W | 0 W | 300 W | battery full: bypass all solar to home |
| 127 | 500 W | 300 W | not full | 200 W | 0 W | 500 W | solar + battery cover demand |
| 128 | 500 W | 500 W | any | 0 W | 0 W | 500 W | solar passes to home, battery idle |


## MATCHING_DISCHARGE Mode — Power Mappings

**Test data:** [`tests/manager_modes/matching_discharge.csv`](../tests/manager_modes/matching_discharge.csv)

`max(self.produced, setpoint)` — only discharges, **never** charges (surplus solar is exported, not stored). Discharge is floored at `self.produced` (≥ 0), so all solar always passes to home and the battery only covers the gap when demand exceeds PV; a negative setpoint just yields solar-only. FULL battery bypasses all solar. SOCEMPTY limits output to solar only.

| # | P1 | PV | SoC State | Battery Discharging | Battery Charging | Device to grid | Notes |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 1 | -300 W | 0 W | any | 0 W | 0 W | 0 W | negative P1 clamped to 0, idle |
| 2 | -300 W | 50 W | any | 0 W | 0 W | 50 W | solar passes to home, battery idle |
| 3 | -300 W | 100 W | any | 0 W | 0 W | 100 W | solar passes to home, battery idle |
| 4 | -300 W | 200 W | any | 0 W | 0 W | 200 W | solar passes to home, battery idle |
| 5 | -100 W | 0 W | any | 0 W | 0 W | 0 W | negative P1 clamped to 0, idle |
| 6 | -100 W | 50 W | any | 0 W | 0 W | 50 W | solar passes to home, battery idle |
| 7 | -100 W | 100 W | any | 0 W | 0 W | 100 W | solar passes to home, battery idle |
| 8 | -100 W | 200 W | any | 0 W | 0 W | 200 W | solar passes to home, battery idle |
| 9 | 0 W | 0 W | any | 0 W | 0 W | 0 W | idle, nothing to do |
| 10 | 0 W | 50 W | any | 0 W | 0 W | 50 W | solar passes to home, battery idle |
| 11 | 0 W | 100 W | any | 0 W | 0 W | 100 W | solar passes to home, battery idle |
| 12 | 0 W | 200 W | any | 0 W | 0 W | 200 W | solar passes to home, battery idle |
| 13 | 100 W | 0 W | EMPTY | 0 W | 0 W | 0 W | can't discharge, P1 unmatched |
| 14 | 100 W | 0 W | FULL | 0 W | 0 W | 0 W | nothing to give |
| 15 | 100 W | 0 W | not full | 100 W | 0 W | 100 W | pure battery discharge |
| 16 | 100 W | 50 W | EMPTY | 0 W | 0 W | 50 W | partial match, solar only |
| 17 | 100 W | 50 W | FULL | 0 W | 0 W | 50 W | bypass only, partial match |
| 18 | 100 W | 50 W | not full | 50 W | 0 W | 100 W | 50 W solar + 50 W battery = matches P1 |
| 19 | 100 W | 100 W | any | 0 W | 0 W | 100 W | solar passes to home, battery idle |
| 20 | 100 W | 200 W | any | 0 W | 0 W | 200 W | solar passes to home, battery idle |
| 21 | 200 W | 0 W | EMPTY | 0 W | 0 W | 0 W | can't discharge, P1 unmatched |
| 22 | 200 W | 0 W | FULL | 0 W | 0 W | 0 W | nothing to give |
| 23 | 200 W | 0 W | not full | 200 W | 0 W | 200 W | pure battery discharge |
| 24 | 200 W | 50 W | EMPTY | 0 W | 0 W | 50 W | solar passes to home, battery idle |
| 25 | 200 W | 50 W | FULL | 0 W | 0 W | 50 W | battery full: bypass all solar to home |
| 26 | 200 W | 50 W | not full | 150 W | 0 W | 200 W | solar + battery cover demand |
| 27 | 200 W | 100 W | EMPTY | 0 W | 0 W | 100 W | can't discharge, solar only |
| 28 | 200 W | 100 W | FULL | 0 W | 0 W | 100 W | bypass only, partial match |
| 29 | 200 W | 100 W | not full | 100 W | 0 W | 200 W | 100 W solar + 100 W battery = matches P1 |
| 30 | 200 W | 200 W | any | 0 W | 0 W | 200 W | solar passes to home, battery idle |
| 31 | 300 W | 0 W | EMPTY | 0 W | 0 W | 0 W | can't discharge, P1 unmatched |
| 32 | 300 W | 0 W | FULL | 0 W | 0 W | 0 W | nothing to give |
| 33 | 300 W | 0 W | not full | 300 W | 0 W | 300 W | high demand, pure battery |
| 34 | 300 W | 50 W | EMPTY | 0 W | 0 W | 50 W | solar passes to home, battery idle |
| 35 | 300 W | 50 W | FULL | 0 W | 0 W | 50 W | battery full: bypass all solar to home |
| 36 | 300 W | 50 W | not full | 250 W | 0 W | 300 W | solar + battery cover demand |
| 37 | 300 W | 100 W | EMPTY | 0 W | 0 W | 100 W | solar passes to home, battery idle |
| 38 | 300 W | 100 W | FULL | 0 W | 0 W | 100 W | battery full: bypass all solar to home |
| 39 | 300 W | 100 W | not full | 200 W | 0 W | 300 W | solar + battery cover demand |
| 40 | 300 W | 200 W | EMPTY | 0 W | 0 W | 200 W | solar passes to home, battery idle |
| 41 | 300 W | 200 W | FULL | 0 W | 0 W | 200 W | battery full: bypass all solar to home |
| 42 | 300 W | 200 W | not full | 100 W | 0 W | 300 W | solar + battery cover demand |
| 43 | 500 W | 0 W | EMPTY | 0 W | 0 W | 0 W | idle, nothing to do |
| 44 | 500 W | 0 W | FULL | 0 W | 0 W | 0 W | idle, nothing to bypass |
| 45 | 500 W | 0 W | not full | 500 W | 0 W | 500 W | pure battery discharge |
| 46 | 500 W | 50 W | EMPTY | 0 W | 0 W | 50 W | solar passes to home, battery idle |
| 47 | 500 W | 50 W | FULL | 0 W | 0 W | 50 W | battery full: bypass all solar to home |
| 48 | 500 W | 50 W | not full | 450 W | 0 W | 500 W | solar + battery cover demand |
| 49 | 500 W | 100 W | EMPTY | 0 W | 0 W | 100 W | solar passes to home, battery idle |
| 50 | 500 W | 100 W | FULL | 0 W | 0 W | 100 W | battery full: bypass all solar to home |
| 51 | 500 W | 100 W | not full | 400 W | 0 W | 500 W | solar + battery cover demand |
| 52 | 500 W | 200 W | EMPTY | 0 W | 0 W | 200 W | can't discharge, solar only |
| 53 | 500 W | 200 W | FULL | 0 W | 0 W | 200 W | bypass only, can't fully match P1 |
| 54 | 500 W | 200 W | not full | 300 W | 0 W | 500 W | battery + solar combined |


## MATCHING_CHARGE Mode — Power Mappings

**Test data:** [`tests/manager_modes/matching_charge.csv`](../tests/manager_modes/matching_charge.csv)

`min(produced, setpoint)` — only solar passes through to home, battery is **never** discharged. P1 > 0: output limited to available solar, battery preserved. P1 < 0: charges battery from available solar (never from grid). P1 = 0: all solar charges battery. FULL battery bypasses all solar to home. SOCEMPTY charges excess solar (can charge, can't discharge).

| # | P1 | PV | SoC State | Battery Discharging | Battery Charging | Device to grid | Notes |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 1 | -300 W | 0 W | any | 0 W | 0 W | 0 W | idle, nothing to do |
| 2 | -300 W | 50 W | EMPTY | 0 W | 50 W | 0 W | all solar stored in battery |
| 3 | -300 W | 50 W | FULL | 0 W | 0 W | 50 W | battery full: bypass all solar to home |
| 4 | -300 W | 50 W | not full | 0 W | 50 W | 0 W | all solar stored in battery |
| 5 | -300 W | 100 W | EMPTY | 0 W | 100 W | 0 W | all solar stored in battery |
| 6 | -300 W | 100 W | FULL | 0 W | 0 W | 100 W | battery full: bypass all solar to home |
| 7 | -300 W | 100 W | not full | 0 W | 100 W | 0 W | all solar stored in battery |
| 8 | -300 W | 200 W | EMPTY | 0 W | 200 W | 0 W | charge capped at available solar |
| 9 | -300 W | 200 W | FULL | 0 W | 0 W | 200 W | bypass overrides, solar to home |
| 10 | -300 W | 200 W | not full | 0 W | 200 W | 0 W | charge capped at available solar |
| 11 | -300 W | 300 W | EMPTY | 0 W | 300 W | 0 W | all solar stored in battery |
| 12 | -300 W | 300 W | FULL | 0 W | 0 W | 300 W | battery full: bypass all solar to home |
| 13 | -300 W | 300 W | not full | 0 W | 300 W | 0 W | all solar stored in battery |
| 14 | -300 W | 500 W | EMPTY | 0 W | 500 W | 0 W | charge from all available solar |
| 15 | -300 W | 500 W | FULL | 0 W | 0 W | 500 W | bypass overrides, solar to home |
| 16 | -300 W | 500 W | not full | 0 W | 500 W | 0 W | charge from all available solar |
| 17 | -100 W | 0 W | any | 0 W | 0 W | 0 W | nothing to charge from |
| 18 | -100 W | 50 W | EMPTY | 0 W | 50 W | 0 W | all solar stored in battery |
| 19 | -100 W | 50 W | FULL | 0 W | 0 W | 50 W | battery full: bypass all solar to home |
| 20 | -100 W | 50 W | not full | 0 W | 50 W | 0 W | all solar stored in battery |
| 21 | -100 W | 100 W | EMPTY | 0 W | 100 W | 0 W | solar stored in battery |
| 22 | -100 W | 100 W | FULL | 0 W | 0 W | 100 W | bypass sends solar to home |
| 23 | -100 W | 100 W | not full | 0 W | 100 W | 0 W | solar stored in battery |
| 24 | -100 W | 200 W | EMPTY | 0 W | 200 W | 0 W | all solar stored in battery |
| 25 | -100 W | 200 W | FULL | 0 W | 0 W | 200 W | bypass all solar to home |
| 26 | -100 W | 200 W | not full | 0 W | 200 W | 0 W | all solar stored in battery |
| 27 | -100 W | 300 W | EMPTY | 0 W | 300 W | 0 W | all solar stored in battery |
| 28 | -100 W | 300 W | FULL | 0 W | 0 W | 300 W | battery full: bypass all solar to home |
| 29 | -100 W | 300 W | not full | 0 W | 300 W | 0 W | all solar stored in battery |
| 30 | -100 W | 500 W | EMPTY | 0 W | 500 W | 0 W | all solar stored in battery |
| 31 | -100 W | 500 W | FULL | 0 W | 0 W | 500 W | battery full: bypass all solar to home |
| 32 | -100 W | 500 W | not full | 0 W | 500 W | 0 W | all solar stored in battery |
| 33 | 0 W | 0 W | any | 0 W | 0 W | 0 W | everything idle |
| 34 | 0 W | 50 W | EMPTY | 0 W | 50 W | 0 W | all solar stored in battery |
| 35 | 0 W | 50 W | FULL | 0 W | 0 W | 50 W | battery full: bypass all solar to home |
| 36 | 0 W | 50 W | not full | 0 W | 50 W | 0 W | all solar stored in battery |
| 37 | 0 W | 100 W | EMPTY | 0 W | 100 W | 0 W | all solar stored in battery |
| 38 | 0 W | 100 W | FULL | 0 W | 0 W | 100 W | battery full: bypass all solar to home |
| 39 | 0 W | 100 W | not full | 0 W | 100 W | 0 W | all solar stored in battery |
| 40 | 0 W | 200 W | EMPTY | 0 W | 200 W | 0 W | all solar charges battery |
| 41 | 0 W | 200 W | FULL | 0 W | 0 W | 200 W | bypass passes solar to home |
| 42 | 0 W | 200 W | not full | 0 W | 200 W | 0 W | all solar stored in battery |
| 43 | 0 W | 300 W | EMPTY | 0 W | 300 W | 0 W | all solar stored in battery |
| 44 | 0 W | 300 W | FULL | 0 W | 0 W | 300 W | battery full: bypass all solar to home |
| 45 | 0 W | 300 W | not full | 0 W | 300 W | 0 W | all solar stored in battery |
| 46 | 0 W | 500 W | EMPTY | 0 W | 500 W | 0 W | all solar stored in battery |
| 47 | 0 W | 500 W | FULL | 0 W | 0 W | 500 W | battery full: bypass all solar to home |
| 48 | 0 W | 500 W | not full | 0 W | 500 W | 0 W | all solar stored in battery |
| 49 | 100 W | 0 W | any | 0 W | 0 W | 0 W | no solar, battery preserved — P1 unmatched |
| 50 | 100 W | 50 W | any | 0 W | 0 W | 50 W | solar passes to home, battery idle |
| 51 | 100 W | 100 W | any | 0 W | 0 W | 100 W | solar passes to home, battery idle |
| 52 | 100 W | 200 W | EMPTY | 0 W | 100 W | 100 W | solar covers P1, 100 W excess charges battery |
| 53 | 100 W | 200 W | FULL | 0 W | 0 W | 200 W | bypass sends all solar to home |
| 54 | 100 W | 200 W | not full | 0 W | 100 W | 100 W | solar covers P1, 100 W excess charges battery |
| 55 | 100 W | 300 W | EMPTY | 0 W | 200 W | 100 W | solar covers P1, 200 W excess charges battery |
| 56 | 100 W | 300 W | FULL | 0 W | 0 W | 300 W | bypass sends all solar to home |
| 57 | 100 W | 300 W | not full | 0 W | 200 W | 100 W | solar covers P1, 200 W excess charges battery |
| 58 | 100 W | 500 W | EMPTY | 0 W | 400 W | 100 W | surplus solar charges battery |
| 59 | 100 W | 500 W | FULL | 0 W | 0 W | 500 W | battery full: bypass all solar to home |
| 60 | 100 W | 500 W | not full | 0 W | 400 W | 100 W | surplus solar charges battery |
| 61 | 300 W | 0 W | any | 0 W | 0 W | 0 W | idle, nothing to do |
| 62 | 300 W | 50 W | any | 0 W | 0 W | 50 W | solar passes to home, battery idle |
| 63 | 300 W | 100 W | any | 0 W | 0 W | 100 W | solar passes to home, battery idle |
| 64 | 300 W | 200 W | any | 0 W | 0 W | 200 W | solar passes to home, battery idle |
| 65 | 300 W | 300 W | any | 0 W | 0 W | 300 W | solar passes to home, battery idle |
| 66 | 300 W | 500 W | EMPTY | 0 W | 200 W | 300 W | surplus solar charges battery |
| 67 | 300 W | 500 W | FULL | 0 W | 0 W | 500 W | battery full: bypass all solar to home |
| 68 | 300 W | 500 W | not full | 0 W | 200 W | 300 W | surplus solar charges battery |
| 69 | 500 W | 0 W | any | 0 W | 0 W | 0 W | idle, nothing to do |
| 70 | 500 W | 50 W | any | 0 W | 0 W | 50 W | solar passes to home, battery idle |
| 71 | 500 W | 100 W | any | 0 W | 0 W | 100 W | solar passes to home, battery idle |
| 72 | 500 W | 200 W | any | 0 W | 0 W | 200 W | solar passes to home, battery idle |
| 73 | 500 W | 300 W | any | 0 W | 0 W | 300 W | solar passes to home, battery idle |
| 74 | 500 W | 500 W | any | 0 W | 0 W | 500 W | solar passes to home, battery idle |

## STORE_SOLAR Mode — Power Mappings

**Test data:** [`tests/manager_modes/store_solar.csv`](../tests/manager_modes/store_solar.csv)

`power_charge(min(0, setpoint))` — all solar goes to battery, **never** to home when P1 > 0. Battery is preserved (never discharged). P1 < 0: charges battery from available solar (never from grid). P1 = 0: all solar charges battery. Only FULL bypass can override and send solar to home. SOCEMPTY charges excess solar (can charge, can't discharge).

| # | P1 | PV | SoC State | Battery Discharging | Battery Charging | Device to grid | Notes |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 1 | -300 W | 0 W | any | 0 W | 0 W | 0 W | idle, nothing to do |
| 2 | -300 W | 50 W | EMPTY | 0 W | 50 W | 0 W | all solar stored in battery |
| 3 | -300 W | 50 W | FULL | 0 W | 0 W | 50 W | battery full: bypass all solar to home |
| 4 | -300 W | 50 W | not full | 0 W | 50 W | 0 W | all solar stored in battery |
| 5 | -300 W | 100 W | EMPTY | 0 W | 100 W | 0 W | all solar stored in battery |
| 6 | -300 W | 100 W | FULL | 0 W | 0 W | 100 W | battery full: bypass all solar to home |
| 7 | -300 W | 100 W | not full | 0 W | 100 W | 0 W | all solar stored in battery |
| 8 | -300 W | 200 W | EMPTY | 0 W | 200 W | 0 W | charge capped at available solar |
| 9 | -300 W | 200 W | FULL | 0 W | 0 W | 200 W | bypass overrides, solar to home |
| 10 | -300 W | 200 W | not full | 0 W | 200 W | 0 W | charge capped at available solar |
| 11 | -300 W | 300 W | EMPTY | 0 W | 300 W | 0 W | all solar stored in battery |
| 12 | -300 W | 300 W | FULL | 0 W | 0 W | 300 W | battery full: bypass all solar to home |
| 13 | -300 W | 300 W | not full | 0 W | 300 W | 0 W | all solar stored in battery |
| 14 | -300 W | 500 W | EMPTY | 0 W | 500 W | 0 W | charge from all available solar |
| 15 | -300 W | 500 W | FULL | 0 W | 0 W | 500 W | bypass overrides, solar to home |
| 16 | -300 W | 500 W | not full | 0 W | 500 W | 0 W | charge from all available solar |
| 17 | -100 W | 0 W | any | 0 W | 0 W | 0 W | nothing to charge from |
| 18 | -100 W | 50 W | EMPTY | 0 W | 50 W | 0 W | all solar stored in battery |
| 19 | -100 W | 50 W | FULL | 0 W | 0 W | 50 W | battery full: bypass all solar to home |
| 20 | -100 W | 50 W | not full | 0 W | 50 W | 0 W | all solar stored in battery |
| 21 | -100 W | 100 W | EMPTY | 0 W | 100 W | 0 W | solar stored in battery |
| 22 | -100 W | 100 W | FULL | 0 W | 0 W | 100 W | bypass sends solar to home |
| 23 | -100 W | 100 W | not full | 0 W | 100 W | 0 W | solar stored in battery |
| 24 | -100 W | 200 W | EMPTY | 0 W | 200 W | 0 W | all solar stored in battery |
| 25 | -100 W | 200 W | FULL | 0 W | 0 W | 200 W | bypass all solar to home |
| 26 | -100 W | 200 W | not full | 0 W | 200 W | 0 W | all solar stored in battery |
| 27 | -100 W | 300 W | EMPTY | 0 W | 300 W | 0 W | all solar stored in battery |
| 28 | -100 W | 300 W | FULL | 0 W | 0 W | 300 W | battery full: bypass all solar to home |
| 29 | -100 W | 300 W | not full | 0 W | 300 W | 0 W | all solar stored in battery |
| 30 | -100 W | 500 W | EMPTY | 0 W | 500 W | 0 W | all solar stored in battery |
| 31 | -100 W | 500 W | FULL | 0 W | 0 W | 500 W | battery full: bypass all solar to home |
| 32 | -100 W | 500 W | not full | 0 W | 500 W | 0 W | all solar stored in battery |
| 33 | 0 W | 0 W | any | 0 W | 0 W | 0 W | everything idle |
| 34 | 0 W | 50 W | EMPTY | 0 W | 50 W | 0 W | all solar stored in battery |
| 35 | 0 W | 50 W | FULL | 0 W | 0 W | 50 W | battery full: bypass all solar to home |
| 36 | 0 W | 50 W | not full | 0 W | 50 W | 0 W | all solar stored in battery |
| 37 | 0 W | 100 W | EMPTY | 0 W | 100 W | 0 W | all solar stored in battery |
| 38 | 0 W | 100 W | FULL | 0 W | 0 W | 100 W | battery full: bypass all solar to home |
| 39 | 0 W | 100 W | not full | 0 W | 100 W | 0 W | all solar stored in battery |
| 40 | 0 W | 200 W | EMPTY | 0 W | 200 W | 0 W | solar charges empty battery |
| 41 | 0 W | 200 W | FULL | 0 W | 0 W | 200 W | bypass passes solar to home |
| 42 | 0 W | 200 W | not full | 0 W | 200 W | 0 W | all solar stored in battery |
| 43 | 0 W | 300 W | EMPTY | 0 W | 300 W | 0 W | all solar stored in battery |
| 44 | 0 W | 300 W | FULL | 0 W | 0 W | 300 W | battery full: bypass all solar to home |
| 45 | 0 W | 300 W | not full | 0 W | 300 W | 0 W | all solar stored in battery |
| 46 | 0 W | 500 W | EMPTY | 0 W | 500 W | 0 W | all solar stored in battery |
| 47 | 0 W | 500 W | FULL | 0 W | 0 W | 500 W | battery full: bypass all solar to home |
| 48 | 0 W | 500 W | not full | 0 W | 500 W | 0 W | all solar stored in battery |
| 49 | 100 W | 0 W | any | 0 W | 0 W | 0 W | no solar, everything idle |
| 50 | 100 W | 50 W | EMPTY | 0 W | 50 W | 0 W | all solar stored in battery |
| 51 | 100 W | 50 W | FULL | 0 W | 0 W | 50 W | bypass only |
| 52 | 100 W | 50 W | not full | 0 W | 50 W | 0 W | all solar stored, nothing to home |
| 53 | 100 W | 100 W | EMPTY | 0 W | 100 W | 0 W | all solar stored in battery |
| 54 | 100 W | 100 W | FULL | 0 W | 0 W | 100 W | battery full: bypass all solar to home |
| 55 | 100 W | 100 W | not full | 0 W | 100 W | 0 W | all solar stored in battery |
| 56 | 100 W | 200 W | EMPTY | 0 W | 200 W | 0 W | solar charges empty battery |
| 57 | 100 W | 200 W | FULL | 0 W | 0 W | 200 W | bypass sends all solar to home |
| 58 | 100 W | 200 W | not full | 0 W | 200 W | 0 W | all solar stored, nothing to home |
| 59 | 100 W | 300 W | EMPTY | 0 W | 300 W | 0 W | all solar stored in battery |
| 60 | 100 W | 300 W | FULL | 0 W | 0 W | 300 W | bypass sends all solar to home |
| 61 | 100 W | 300 W | not full | 0 W | 300 W | 0 W | all solar stored, P1 unmatched |
| 62 | 100 W | 500 W | EMPTY | 0 W | 500 W | 0 W | all solar stored in battery |
| 63 | 100 W | 500 W | FULL | 0 W | 0 W | 500 W | bypass sends all solar to home |
| 64 | 100 W | 500 W | not full | 0 W | 500 W | 0 W | all solar stored, P1 unmatched |
| 65 | 300 W | 0 W | any | 0 W | 0 W | 0 W | idle, nothing to do |
| 66 | 300 W | 50 W | EMPTY | 0 W | 50 W | 0 W | all solar stored in battery |
| 67 | 300 W | 50 W | FULL | 0 W | 0 W | 50 W | battery full: bypass all solar to home |
| 68 | 300 W | 50 W | not full | 0 W | 50 W | 0 W | all solar stored in battery |
| 69 | 300 W | 100 W | EMPTY | 0 W | 100 W | 0 W | all solar stored in battery |
| 70 | 300 W | 100 W | FULL | 0 W | 0 W | 100 W | battery full: bypass all solar to home |
| 71 | 300 W | 100 W | not full | 0 W | 100 W | 0 W | all solar stored in battery |
| 72 | 300 W | 200 W | EMPTY | 0 W | 200 W | 0 W | all solar stored in battery |
| 73 | 300 W | 200 W | FULL | 0 W | 0 W | 200 W | bypass only |
| 74 | 300 W | 200 W | not full | 0 W | 200 W | 0 W | all solar stored, P1 unmatched |
| 75 | 300 W | 300 W | EMPTY | 0 W | 300 W | 0 W | all solar stored in battery |
| 76 | 300 W | 300 W | FULL | 0 W | 0 W | 300 W | battery full: bypass all solar to home |
| 77 | 300 W | 300 W | not full | 0 W | 300 W | 0 W | all solar stored in battery |
| 78 | 300 W | 500 W | EMPTY | 0 W | 500 W | 0 W | all solar stored in battery |
| 79 | 300 W | 500 W | FULL | 0 W | 0 W | 500 W | battery full: bypass all solar to home |
| 80 | 300 W | 500 W | not full | 0 W | 500 W | 0 W | all solar stored in battery |

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
| 1 | +300 W | 0 W | EMPTY | 0 W | 0 W | 0 W | can't discharge, no solar |
| 2 | +300 W | 0 W | FULL | 0 W | 0 W | 0 W | nothing to bypass |
| 3 | +300 W | 0 W | not full | 300 W | 0 W | 300 W | pure battery discharge |
| 4 | +300 W | 200 W | EMPTY | 0 W | 0 W | 200 W | can't discharge, solar passes to home |
| 5 | +300 W | 200 W | FULL | 0 W | 0 W | 200 W | bypass caps output at PV |
| 6 | +300 W | 200 W | not full | 100 W | 0 W | 300 W | solar covers 200 W, battery covers 100 W |
| 7 | +300 W | 50 W | EMPTY | 0 W | 0 W | 50 W | can't discharge, solar only |
| 8 | +300 W | 50 W | FULL | 0 W | 0 W | 50 W | bypass only |
| 9 | +300 W | 50 W | not full | 250 W | 0 W | 300 W | mostly battery discharge |
| 10 | +300 W | 500 W | EMPTY | 0 W | 200 W | 300 W | can't discharge; solar covers 300 W output, 200 W excess charges battery |
| 11 | +300 W | 500 W | FULL | 0 W | 0 W | 500 W | bypass overrides manual setpoint |
| 12 | +300 W | 500 W | not full | 0 W | 200 W | 300 W | solar covers all output, 200 W excess charges battery |
| 13 | +100 W | 0 W | EMPTY | 0 W | 0 W | 0 W | can't discharge, no solar |
| 14 | +100 W | 0 W | FULL | 0 W | 0 W | 0 W | nothing to bypass |
| 15 | +100 W | 0 W | not full | 100 W | 0 W | 100 W | pure battery discharge |
| 16 | +100 W | 200 W | EMPTY | 0 W | 100 W | 100 W | can't discharge; solar covers 100 W output, 100 W excess charges battery |
| 17 | +100 W | 200 W | FULL | 0 W | 0 W | 200 W | bypass overrides, all solar to home |
| 18 | +100 W | 200 W | not full | 0 W | 100 W | 100 W | solar covers all output, 100 W excess charges battery |
| 19 | +100 W | 50 W | EMPTY | 0 W | 0 W | 50 W | can't discharge, solar only |
| 20 | +100 W | 50 W | FULL | 0 W | 0 W | 50 W | bypass only |
| 21 | +100 W | 50 W | not full | 50 W | 0 W | 100 W | 50W solar + 50W battery |
| 22 | +50 W | 0 W | EMPTY | 0 W | 0 W | 0 W | can't discharge, no solar |
| 23 | +50 W | 0 W | FULL | 0 W | 0 W | 0 W | nothing to bypass |
| 24 | +50 W | 0 W | not full | 50 W | 0 W | 50 W | pure battery discharge |
| 25 | +50 W | 200 W | EMPTY | 0 W | 150 W | 50 W | can't discharge; solar covers 50 W output, 150 W excess charges battery |
| 26 | +50 W | 200 W | FULL | 0 W | 0 W | 200 W | bypass overrides, all solar to home |
| 27 | +50 W | 200 W | not full | 0 W | 150 W | 50 W | solar covers all output, 150 W excess charges battery |
| 28 | +50 W | 50 W | EMPTY | 0 W | 0 W | 50 W | can't discharge, solar only |
| 29 | +50 W | 50 W | FULL | 0 W | 0 W | 50 W | bypass only |
| 30 | +50 W | 50 W | not full | 0 W | 0 W | 50 W | solar covers manual output exactly, battery neutral |
| 31 | 0 W | 0 W | EMPTY | 0 W | 0 W | 0 W | idle, nothing to do |
| 32 | 0 W | 0 W | FULL | 0 W | 0 W | 0 W | idle, nothing to bypass |
| 33 | 0 W | 0 W | not full | 0 W | 0 W | 0 W | all idle |
| 34 | 0 W | 200 W | EMPTY | 0 W | 200 W | 0 W | solar charges empty battery |
| 35 | 0 W | 200 W | FULL | 0 W | 0 W | 200 W | FULL battery bypasses solar to home |
| 36 | 0 W | 200 W | not full | 0 W | 200 W | 0 W | solar charges battery |
| 37 | -50 W | 0 W | EMPTY | 0 W | 50 W | -50 W | full grid charging |
| 38 | -50 W | 0 W | FULL | 0 W | 0 W | 0 W | can't charge a full battery |
| 39 | -50 W | 0 W | not full | 0 W | 50 W | -50 W | full grid charging |
| 40 | -50 W | 200 W | EMPTY | 0 W | 250 W | -50 W | 50 W from grid + 200 W solar into battery; net grid draw 50 W |
| 41 | -50 W | 200 W | FULL | 0 W | 0 W | 200 W | battery full, can't charge; bypass sends all solar to home |
| 42 | -50 W | 200 W | not full | 0 W | 250 W | -50 W | 50 W from grid + 200 W solar into battery; net grid draw 50 W |
| 43 | -100 W | 0 W | EMPTY | 0 W | 100 W | -100 W | full grid charging |
| 44 | -100 W | 0 W | FULL | 0 W | 0 W | 0 W | can't charge a full battery |
| 45 | -100 W | 0 W | not full | 0 W | 100 W | -100 W | full grid charging |
| 46 | -100 W | 200 W | EMPTY | 0 W | 300 W | -100 W | 100 W from grid + 200 W solar into battery; net grid draw 100 W |
| 47 | -100 W | 200 W | FULL | 0 W | 0 W | 200 W | battery full, can't charge; bypass sends all solar to home |
| 48 | -100 W | 200 W | not full | 0 W | 300 W | -100 W | 100 W from grid + 200 W solar into battery; net grid draw 100 W |
| 49 | −300 W | 0 W | EMPTY | 0 W | 300 W | −300 W | full grid charging |
| 50 | −300 W | 0 W | FULL | 0 W | 0 W | 0 W | can't charge a full battery |
| 51 | −300 W | 0 W | not full | 0 W | 300 W | −300 W | full grid charging |
| 52 | −300 W | 200 W | EMPTY | 0 W | 500 W | −300 W | 300 W from grid + 200 W solar into battery; net grid draw 300 W |
| 53 | −300 W | 200 W | FULL | 0 W | 0 W | 200 W | battery full, can't charge; bypass sends all solar to home |
| 54 | −300 W | 200 W | not full | 0 W | 500 W | −300 W | 300 W from grid + 200 W solar into battery; net grid draw 300 W |
| 55 | −300 W | 500 W | EMPTY | 0 W | 800 W | −300 W | 300 W from grid + 500 W solar into battery; net grid draw 300 W |
| 56 | −300 W | 500 W | FULL | 0 W | 0 W | 500 W | battery full, can't charge; bypass sends all solar to home |
| 57 | −300 W | 500 W | not full | 0 W | 800 W | −300 W | 300 W from grid + 500 W solar into battery; net grid draw 300 W |

## MATCHING Mode — Power Mappings

**Test data:** [`tests/manager_modes/matching.csv`](../tests/manager_modes/matching.csv)

`setpoint = P1 ± device contributions` → `power_discharge` (setpoint ≥ 0) or `power_charge` (setpoint < 0) — balances P1 to zero using available PV and battery. P1 > 0: discharges to cover house demand, PV excess charges battery. P1 < 0: charges battery from own available solar only (never from grid — no device can force AC grid charging in this mode); if the export comes from another device it stays unmatched. P1 = 0: all solar charges battery. FULL battery bypasses all solar to home. SOCEMPTY limits output to solar only.

| # | P1 | PV | SoC State | Battery Discharging | Battery Charging | Device to grid | Notes |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 1 | 50 W | 0 W | EMPTY | 0 W | 0 W | 0 W | can't discharge, P1 unmatched |
| 2 | 50 W | 0 W | FULL | 0 W | 0 W | 0 W | nothing to give |
| 3 | 50 W | 0 W | not full | 50 W | 0 W | 50 W | pure battery discharge |
| 4 | 50 W | 50 W | EMPTY | 0 W | 0 W | 50 W | solar covers P1 exactly, can't discharge |
| 5 | 50 W | 50 W | FULL | 0 W | 0 W | 50 W | bypass matches P1 exactly |
| 6 | 50 W | 50 W | not full | 0 W | 0 W | 50 W | solar covers P1 exactly, battery neutral |
| 7 | 50 W | 200 W | EMPTY | 0 W | 150 W | 50 W | solar covers P1, 150 W excess charges battery |
| 8 | 50 W | 200 W | FULL | 0 W | 0 W | 200 W | bypass sends all solar to home |
| 9 | 50 W | 200 W | not full | 0 W | 150 W | 50 W | PV excess charges battery, matches P1 |
| 10 | 100 W | 0 W | EMPTY | 0 W | 0 W | 0 W | can't discharge, P1 unmatched |
| 11 | 100 W | 0 W | FULL | 0 W | 0 W | 0 W | nothing to give |
| 12 | 100 W | 0 W | not full | 100 W | 0 W | 100 W | pure battery discharge |
| 13 | 100 W | 50 W | EMPTY | 0 W | 0 W | 50 W | partial match, solar only |
| 14 | 100 W | 50 W | FULL | 0 W | 0 W | 50 W | bypass only, can't fully match P1 |
| 15 | 100 W | 50 W | not full | 50 W | 0 W | 100 W | 50 W solar + 50 W battery = matches P1 |
| 16 | 100 W | 100 W | EMPTY | 0 W | 0 W | 100 W | exact balance, battery neutral |
| 17 | 100 W | 100 W | FULL | 0 W | 0 W | 100 W | bypass matches P1 exactly |
| 18 | 100 W | 100 W | not full | 0 W | 0 W | 100 W | solar covers P1 exactly, battery neutral |
| 19 | 100 W | 200 W | EMPTY | 0 W | 100 W | 100 W | solar covers P1, 100 W excess charges battery |
| 20 | 100 W | 200 W | FULL | 0 W | 0 W | 200 W | bypass sends all solar to home |
| 21 | 100 W | 200 W | not full | 0 W | 100 W | 100 W | PV excess charges battery, matches P1 |
| 22 | 100 W | 300 W | EMPTY | 0 W | 200 W | 100 W | solar covers P1, 200 W excess charges battery |
| 23 | 100 W | 300 W | FULL | 0 W | 0 W | 300 W | bypass sends all solar to home |
| 24 | 100 W | 300 W | not full | 0 W | 200 W | 100 W | 200 W PV excess charges battery, matches P1 |
| 25 | 200 W | 0 W | EMPTY | 0 W | 0 W | 0 W | can't discharge, P1 unmatched |
| 26 | 200 W | 0 W | FULL | 0 W | 0 W | 0 W | nothing to give |
| 27 | 200 W | 0 W | not full | 200 W | 0 W | 200 W | pure battery discharge |
| 28 | 200 W | 100 W | EMPTY | 0 W | 0 W | 100 W | can't discharge, solar only (100 W unmatched) |
| 29 | 200 W | 100 W | FULL | 0 W | 0 W | 100 W | bypass only, partial match |
| 30 | 200 W | 100 W | not full | 100 W | 0 W | 200 W | 100 W solar + 100 W battery = matches P1 |
| 31 | 200 W | 200 W | EMPTY | 0 W | 0 W | 200 W | solar covers P1 exactly, can't discharge |
| 32 | 200 W | 200 W | FULL | 0 W | 0 W | 200 W | bypass matches P1 exactly |
| 33 | 200 W | 200 W | not full | 0 W | 0 W | 200 W | solar covers P1 exactly, battery neutral |
| 34 | 300 W | 0 W | EMPTY | 0 W | 0 W | 0 W | can't discharge, P1 unmatched |
| 35 | 300 W | 0 W | FULL | 0 W | 0 W | 0 W | nothing to give |
| 36 | 300 W | 0 W | not full | 300 W | 0 W | 300 W | high demand, pure battery |
| 37 | 500 W | 200 W | EMPTY | 0 W | 0 W | 200 W | can't discharge, solar only |
| 38 | 500 W | 200 W | FULL | 0 W | 0 W | 200 W | bypass only, can't fully match P1 |
| 39 | 500 W | 200 W | not full | 300 W | 0 W | 500 W | battery + solar combined |
| 40 | 0 W | 0 W | EMPTY | 0 W | 0 W | 0 W | idle, nothing to do |
| 41 | 0 W | 0 W | FULL | 0 W | 0 W | 0 W | idle, nothing to bypass |
| 42 | 0 W | 0 W | not full | 0 W | 0 W | 0 W | everything idle |
| 43 | 0 W | 200 W | EMPTY | 0 W | 200 W | 0 W | all solar stored in battery |
| 44 | 0 W | 200 W | FULL | 0 W | 0 W | 200 W | bypass passes solar to home |
| 45 | 0 W | 200 W | not full | 0 W | 200 W | 0 W | all solar stored in battery |
| 46 | −100 W | 0 W | EMPTY | 0 W | 0 W | 0 W | no own solar; can't charge from grid → P1 unmatched |
| 47 | −100 W | 0 W | FULL | 0 W | 0 W | 0 W | battery full and no solar; can't charge from grid → P1 unmatched |
| 48 | −100 W | 0 W | not full | 0 W | 0 W | 0 W | no own solar; can't charge from grid → P1 unmatched |
| 49 | −100 W | 100 W | EMPTY | 0 W | 100 W | 0 W | solar stored in battery |
| 50 | −100 W | 100 W | FULL | 0 W | 0 W | 100 W | bypass sends solar to home |
| 51 | −100 W | 100 W | not full | 0 W | 100 W | 0 W | solar stored in battery |
| 52 | −100 W | 200 W | EMPTY | 0 W | 200 W | 0 W | store all available solar; can't charge from grid |
| 53 | −100 W | 200 W | FULL | 0 W | 0 W | 200 W | bypass all solar to home |
| 54 | −100 W | 200 W | not full | 0 W | 200 W | 0 W | store all available solar; can't charge from grid |
| 55 | −300 W | 500 W | EMPTY | 0 W | 500 W | 0 W | store all available solar; can't charge from grid |
| 56 | −300 W | 500 W | FULL | 0 W | 0 W | 500 W | bypass overrides, solar to home |
| 57 | −300 W | 500 W | not full | 0 W | 500 W | 0 W | store all available solar; can't charge from grid |


## MATCHING_DISCHARGE Mode — Power Mappings

**Test data:** [`tests/manager_modes/matching_discharge.csv`](../tests/manager_modes/matching_discharge.csv)

`max(0, setpoint)` — only discharges, **never** charges from grid. Negative P1 is clamped to 0. Devices discharge to cover P1 (using PV + battery) or stay idle. Solar always passes to home even when P1 = 0. FULL battery bypasses all solar. SOCEMPTY limits output to solar only.

| # | P1 | PV | SoC State | Battery Discharging | Battery Charging | Device to grid | Notes |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 1 | 100 W | 0 W | EMPTY | 0 W | 0 W | 0 W | can't discharge, P1 unmatched |
| 2 | 100 W | 0 W | FULL | 0 W | 0 W | 0 W | nothing to give |
| 3 | 100 W | 0 W | not full | 100 W | 0 W | 100 W | pure battery discharge |
| 4 | 100 W | 50 W | EMPTY | 0 W | 0 W | 50 W | partial match, solar only |
| 5 | 100 W | 50 W | FULL | 0 W | 0 W | 50 W | bypass only, partial match |
| 6 | 100 W | 50 W | not full | 50 W | 0 W | 100 W | 50 W solar + 50 W battery = matches P1 |
| 7 | 100 W | 100 W | EMPTY | 0 W | 0 W | 100 W | exact balance, battery neutral |
| 8 | 100 W | 100 W | FULL | 0 W | 0 W | 100 W | bypass matches P1 exactly |
| 9 | 100 W | 100 W | not full | 0 W | 0 W | 100 W | solar covers P1 exactly, battery neutral |
| 10 | 100 W | 200 W | EMPTY | 0 W | 0 W | 200 W | solar passes to home, battery idle |
| 11 | 100 W | 200 W | FULL | 0 W | 0 W | 200 W | bypass sends all solar to home |
| 12 | 100 W | 200 W | not full | 0 W | 0 W | 200 W | solar passes to home, battery idle (excess exported, not stored) |
| 13 | 200 W | 0 W | EMPTY | 0 W | 0 W | 0 W | can't discharge, P1 unmatched |
| 14 | 200 W | 0 W | FULL | 0 W | 0 W | 0 W | nothing to give |
| 15 | 200 W | 0 W | not full | 200 W | 0 W | 200 W | pure battery discharge |
| 16 | 200 W | 100 W | EMPTY | 0 W | 0 W | 100 W | can't discharge, solar only |
| 17 | 200 W | 100 W | FULL | 0 W | 0 W | 100 W | bypass only, partial match |
| 18 | 200 W | 100 W | not full | 100 W | 0 W | 200 W | 100 W solar + 100 W battery = matches P1 |
| 19 | 200 W | 200 W | EMPTY | 0 W | 0 W | 200 W | solar covers P1 exactly, can't discharge |
| 20 | 200 W | 200 W | FULL | 0 W | 0 W | 200 W | bypass matches P1 exactly |
| 21 | 200 W | 200 W | not full | 0 W | 0 W | 200 W | solar covers P1 exactly, battery neutral |
| 22 | 300 W | 0 W | EMPTY | 0 W | 0 W | 0 W | can't discharge, P1 unmatched |
| 23 | 300 W | 0 W | FULL | 0 W | 0 W | 0 W | nothing to give |
| 24 | 300 W | 0 W | not full | 300 W | 0 W | 300 W | high demand, pure battery |
| 25 | 500 W | 200 W | EMPTY | 0 W | 0 W | 200 W | can't discharge, solar only |
| 26 | 500 W | 200 W | FULL | 0 W | 0 W | 200 W | bypass only, can't fully match P1 |
| 27 | 500 W | 200 W | not full | 300 W | 0 W | 500 W | battery + solar combined |
| 28 | 0 W | 0 W | EMPTY | 0 W | 0 W | 0 W | idle, nothing to do |
| 29 | 0 W | 0 W | FULL | 0 W | 0 W | 0 W | idle, nothing to bypass |
| 30 | 0 W | 0 W | not full | 0 W | 0 W | 0 W | everything idle |
| 31 | 0 W | 200 W | EMPTY | 0 W | 0 W | 200 W | solar passes to home, battery idle |
| 32 | 0 W | 200 W | FULL | 0 W | 0 W | 200 W | bypass passes solar to home |
| 33 | 0 W | 200 W | not full | 0 W | 0 W | 200 W | solar passes to home |
| 34 | −100 W | 0 W | any | 0 W | 0 W | 0 W | negative P1 clamped to 0, idle |
| 35 | −100 W | 100 W | any | 0 W | 0 W | 100 W | solar passes to home, battery idle |
| 36 | −100 W | 200 W | any | 0 W | 0 W | 200 W | solar passes to home, battery idle |
| 37 | −300 W | 0 W | any | 0 W | 0 W | 0 W | negative P1 clamped to 0, idle |
| 38 | −300 W | 200 W | any | 0 W | 0 W | 200 W | solar passes to home, battery idle |


## MATCHING_CHARGE Mode — Power Mappings

**Test data:** [`tests/manager_modes/matching_charge.csv`](../tests/manager_modes/matching_charge.csv)

`min(produced, setpoint)` — only solar passes through to home, battery is **never** discharged. P1 > 0: output limited to available solar, battery preserved. P1 < 0: charges battery from available solar (never from grid). P1 = 0: all solar charges battery. FULL battery bypasses all solar to home. SOCEMPTY charges excess solar (can charge, can't discharge).

| # | P1 | PV | SoC State | Battery Discharging | Battery Charging | Device to grid | Notes |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 1 | 100 W | 0 W | any | 0 W | 0 W | 0 W | no solar, battery preserved — P1 unmatched |
| 2 | 100 W | 100 W | EMPTY | 0 W | 0 W | 100 W | exact balance, battery neutral |
| 3 | 100 W | 100 W | FULL | 0 W | 0 W | 100 W | bypass matches P1 exactly |
| 4 | 100 W | 100 W | not full | 0 W | 0 W | 100 W | exact balance, battery neutral |
| 5 | 100 W | 200 W | EMPTY | 0 W | 100 W | 100 W | solar covers P1, 100 W excess charges battery |
| 6 | 100 W | 200 W | FULL | 0 W | 0 W | 200 W | bypass sends all solar to home |
| 7 | 100 W | 200 W | not full | 0 W | 100 W | 100 W | solar covers P1, 100 W excess charges battery |
| 8 | 100 W | 300 W | EMPTY | 0 W | 200 W | 100 W | solar covers P1, 200 W excess charges battery |
| 9 | 100 W | 300 W | FULL | 0 W | 0 W | 300 W | bypass sends all solar to home |
| 10 | 100 W | 300 W | not full | 0 W | 200 W | 100 W | solar covers P1, 200 W excess charges battery |
| 11 | 100 W | 50 W | EMPTY | 0 W | 0 W | 50 W | solar only, battery does NOT discharge to cover gap |
| 12 | 100 W | 50 W | FULL | 0 W | 0 W | 50 W | bypass only, partial match |
| 13 | 100 W | 50 W | not full | 0 W | 0 W | 50 W | solar only, battery does NOT discharge to cover gap |
| 14 | 300 W | 200 W | EMPTY | 0 W | 0 W | 200 W | solar only, battery does NOT discharge, 100 W gap |
| 15 | 300 W | 200 W | FULL | 0 W | 0 W | 200 W | bypass only, battery preserved |
| 16 | 300 W | 200 W | not full | 0 W | 0 W | 200 W | solar only, battery preserved, 100 W gap |
| 17 | 500 W | 200 W | EMPTY | 0 W | 0 W | 200 W | solar only, battery does NOT discharge, 300 W gap |
| 18 | 500 W | 200 W | FULL | 0 W | 0 W | 200 W | bypass only, large gap |
| 19 | 500 W | 200 W | not full | 0 W | 0 W | 200 W | solar only, battery preserved, 300 W gap |
| 20 | 0 W | 0 W | any | 0 W | 0 W | 0 W | everything idle |
| 21 | 0 W | 200 W | EMPTY | 0 W | 200 W | 0 W | all solar charges battery |
| 22 | 0 W | 200 W | FULL | 0 W | 0 W | 200 W | bypass passes solar to home |
| 23 | 0 W | 200 W | not full | 0 W | 200 W | 0 W | all solar stored in battery |
| 24 | -100 W | 100 W | EMPTY | 0 W | 100 W | 0 W | solar stored in battery |
| 25 | -100 W | 200 W | EMPTY | 0 W | 200 W | 0 W | all solar stored in battery |
| 26 | -300 W | 200 W | EMPTY | 0 W | 200 W | 0 W | charge capped at available solar |
| 27 | -300 W | 200 W | FULL | 0 W | 0 W | 200 W | bypass overrides, solar to home |
| 28 | -300 W | 500 W | EMPTY | 0 W | 500 W | 0 W | charge from all available solar |
| 29 | −100 W | 0 W | any | 0 W | 0 W | 0 W | nothing to charge from |
| 30 | −100 W | 100 W | FULL | 0 W | 0 W | 100 W | bypass sends solar to home |
| 31 | −100 W | 100 W | not full | 0 W | 100 W | 0 W | solar stored in battery |
| 32 | −100 W | 200 W | FULL | 0 W | 0 W | 200 W | bypass all solar to home |
| 33 | −100 W | 200 W | not full | 0 W | 200 W | 0 W | all solar stored in battery |
| 34 | −300 W | 200 W | not full | 0 W | 200 W | 0 W | charge capped at available solar |
| 35 | −300 W | 500 W | FULL | 0 W | 0 W | 500 W | bypass overrides, solar to home |
| 36 | −300 W | 500 W | not full | 0 W | 500 W | 0 W | charge from all available solar |

## STORE_SOLAR Mode — Power Mappings

**Test data:** [`tests/manager_modes/store_solar.csv`](../tests/manager_modes/store_solar.csv)

`power_charge(min(0, setpoint))` — all solar goes to battery, **never** to home when P1 > 0. Battery is preserved (never discharged). P1 < 0: charges battery from available solar (never from grid). P1 = 0: all solar charges battery. Only FULL bypass can override and send solar to home. SOCEMPTY charges excess solar (can charge, can't discharge).

| # | P1 | PV | SoC State | Battery Discharging | Battery Charging | Device to grid | Notes |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 1 | 100 W | 0 W | any | 0 W | 0 W | 0 W | no solar, everything idle |
| 2 | 100 W | 200 W | EMPTY | 0 W | 200 W | 0 W | solar charges empty battery |
| 3 | 100 W | 200 W | FULL | 0 W | 0 W | 200 W | bypass sends all solar to home |
| 4 | 100 W | 200 W | not full | 0 W | 200 W | 0 W | all solar stored, nothing to home |
| 5 | 100 W | 300 W | EMPTY | 0 W | 300 W | 0 W | all solar stored in battery |
| 6 | 100 W | 300 W | FULL | 0 W | 0 W | 300 W | bypass sends all solar to home |
| 7 | 100 W | 300 W | not full | 0 W | 300 W | 0 W | all solar stored, P1 unmatched |
| 8 | 100 W | 50 W | EMPTY | 0 W | 50 W | 0 W | all solar stored in battery |
| 9 | 100 W | 50 W | FULL | 0 W | 0 W | 50 W | bypass only |
| 10 | 100 W | 50 W | not full | 0 W | 50 W | 0 W | all solar stored, nothing to home |
| 11 | 100 W | 500 W | EMPTY | 0 W | 500 W | 0 W | all solar stored in battery |
| 12 | 100 W | 500 W | FULL | 0 W | 0 W | 500 W | bypass sends all solar to home |
| 13 | 100 W | 500 W | not full | 0 W | 500 W | 0 W | all solar stored, P1 unmatched |
| 14 | 300 W | 200 W | EMPTY | 0 W | 200 W | 0 W | all solar stored in battery |
| 15 | 300 W | 200 W | FULL | 0 W | 0 W | 200 W | bypass only |
| 16 | 300 W | 200 W | not full | 0 W | 200 W | 0 W | all solar stored, P1 unmatched |
| 17 | 0 W | 0 W | any | 0 W | 0 W | 0 W | everything idle |
| 18 | 0 W | 200 W | EMPTY | 0 W | 200 W | 0 W | solar charges empty battery |
| 19 | 0 W | 200 W | FULL | 0 W | 0 W | 200 W | bypass passes solar to home |
| 20 | 0 W | 200 W | not full | 0 W | 200 W | 0 W | all solar stored in battery |
| 21 | -100 W | 100 W | EMPTY | 0 W | 100 W | 0 W | solar stored in battery |
| 22 | -100 W | 200 W | EMPTY | 0 W | 200 W | 0 W | all solar stored in battery |
| 23 | -300 W | 200 W | EMPTY | 0 W | 200 W | 0 W | charge capped at available solar |
| 24 | -300 W | 200 W | FULL | 0 W | 0 W | 200 W | bypass overrides, solar to home |
| 25 | -300 W | 500 W | EMPTY | 0 W | 500 W | 0 W | charge from all available solar |
| 26 | −100 W | 0 W | any | 0 W | 0 W | 0 W | nothing to charge from |
| 27 | −100 W | 100 W | FULL | 0 W | 0 W | 100 W | bypass sends solar to home |
| 28 | −100 W | 100 W | not full | 0 W | 100 W | 0 W | solar stored in battery |
| 29 | −100 W | 200 W | FULL | 0 W | 0 W | 200 W | bypass all solar to home |
| 30 | −100 W | 200 W | not full | 0 W | 200 W | 0 W | all solar stored in battery |
| 31 | −300 W | 200 W | not full | 0 W | 200 W | 0 W | charge capped at available solar |
| 32 | −300 W | 500 W | FULL | 0 W | 0 W | 500 W | bypass overrides, solar to home |
| 33 | −300 W | 500 W | not full | 0 W | 500 W | 0 W | charge from all available solar |

# Distributed 3x3 digital LDO: on-chip voltage-sensor measurements

Measured output-voltage waveforms of a 3x3 array of distributed digital
low-dropout regulators (DLDOs) integrated in a 22 nm AI SoC. The nine LDO
units share one VDD grid and one global integrator, which is hosted by the
central unit; each unit has a local proportional path driven by a 3.5 GHz
domino-based time-to-digital converter (TDC) that senses the local voltage.
The waveforms in this repository are the output voltage of the **central
unit**, recorded by the on-chip voltage sensor (two 6-bit channels sampled
every 500 ps by a dual-phase 1 GHz clock) during eight measurement tasks:
four load transients and four dynamic-voltage-scaling (DVS) transitions.
Every task was repeated 64 times; all 64 runs are included, unaveraged.

## Directory

| Path | Content |
|---|---|
| `data/v_sensor_results.xlsx` | Original sensor export: one sheet (`sensor_export`) with the eight tasks side by side, separated by an empty column; measured code columns are green, recovered voltages red |
| `data/csv/01_..08_*.csv` | The same data, one file per task, produced by the script below |
| `scripts/export_csv.py` | Splits the workbook into the CSV files, verifies the time grid and the voltage recovery (`--check` verifies only) |
| `LICENSE` | CC BY 4.0, the license of the data |
| `LICENSES/Apache-2.0.txt` | License of the script |

## Measurement tasks

All tasks were measured at a nominal output of 800 mV unless the task itself
changes the reference. `t` is the time relative to the trigger instant.

| File | Task | Condition | Window | Rows |
|---|---|---|---|---|
| `01_load_slow_vdn` | load transient, voltage droop | load step 144 -> 1004 mA, 20 ns edge | -25 .. +100 ns | 251 |
| `02_load_slow_vup` | load transient, overshoot | load step 1004 -> 144 mA, 20 ns edge | -25 .. +100 ns | 251 |
| `03_load_fast_vdn` | load transient, voltage droop | load step 144 -> 573 mA, 0.2 ns edge | -25 .. +100 ns | 251 |
| `04_load_fast_vup` | load transient, overshoot | load step 573 -> 144 mA, 0.2 ns edge | -25 .. +100 ns | 251 |
| `05_dvs_down_boosting` | DVS down | reference 800 -> 600 mV, DVS repair and boosting enabled | -20 .. +60 ns | 161 |
| `06_dvs_down_repair` | DVS down | reference 800 -> 600 mV, DVS repair only | -20 .. +60 ns | 161 |
| `07_dvs_up_boosting` | DVS up | reference 600 -> 800 mV, DVS repair and boosting enabled | -20 .. +60 ns | 161 |
| `08_dvs_up_repair` | DVS up | reference 600 -> 800 mV, DVS repair only | -20 .. +60 ns | 161 |

The file order is the left-to-right order of the blocks in the workbook.
*DVS repair* is the look-up-table based gain compensation that keeps the loop
stable across the reference change; *boosting* additionally pre-scales the
integrator code to shorten the settling.

### Trigger (`t = 0`)

`t = 0` is the first sample at which the sensed voltage crosses the
task-specific threshold; because the sensor codes are monotonic in the
voltage, each threshold is one code value.

| Tasks | Threshold | Sensor code | Direction |
|---|---|---|---|
| 01, 03 (droop) | 780 mV | `sensor0` = 20 | falling |
| 02, 04 (overshoot) | 820 mV | `sensor0` = 28 | rising |
| 05, 06 (DVS down) | 700 mV | `sensor0` = 4 | falling |
| 07, 08 (DVS up) | 700 mV | `sensor1` = 44 | rising |

## Columns

Every file has 193 columns; `k` runs from 1 to 64 and numbers the repetition.

| Column | Unit | Meaning |
|---|---|---|
| `t` | ns | time relative to the trigger, 0.5 ns per row |
| `sensor0_k` | code 0..47 | high-range sensor channel of run `k`, centred at 800 mV |
| `sensor1_k` | code 0..47 | low-range sensor channel of run `k`, centred at 600 mV |
| `vdd_measured_k` | mV | output voltage of run `k` recovered from the two codes |

Value ranges in the export:

| File | `sensor0` | `sensor1` | `vdd_measured` (mV) |
|---|---|---|---|
| 01 | 9 .. 26 | 47 | 725 .. 810 |
| 02 | 20 .. 31 | 47 | 780 .. 835 |
| 03 | 9 .. 26 | 47 | 725 .. 810 |
| 04 | 21 .. 33 | 47 | 785 .. 845 |
| 05 | 0 .. 25 | 21 .. 47 | 585 .. 805 |
| 06 | 0 .. 25 | 21 .. 47 | 585 .. 805 |
| 07 | 0 .. 29 | 23 .. 47 | 595 .. 825 |
| 08 | 0 .. 32 | 22 .. 47 | 590 .. 840 |

Missing samples: in the export the last sample of the window is absent for
10 of the 64 runs of task 01 (`t = 100 ns`), 11 runs of task 05 and 16 runs
of task 06 (`t = 60 ns`). Those cells are empty in the CSV files; no value
was interpolated.

## Sensor codes and voltage recovery

The two channels are 6-bit codes with the same 5 mV step and complementary
ranges:

```
sensor0 = clip(24 + (V - 800 mV) / 5 mV, 0, 47)   # 0 at V <= 680 mV, 47 at V >= 915 mV
sensor1 = clip(24 + (V - 600 mV) / 5 mV, 0, 47)   # 0 at V <= 480 mV, 47 at V >= 715 mV
```

`sensor0` saturates at 0 for low voltages and `sensor1` at 47 for high
voltages, so at every instant the channel that is not saturated is used:

```
if sensor1 < 47:  V = 600 + 5 * (sensor1 - 24)   # mV
else:             V = 800 + 5 * (sensor0 - 24)
```

This is exactly how `vdd_measured_k` was computed from `sensor0_k` and
`sensor1_k`; `scripts/export_csv.py --check` re-applies the formula to every
cell and stops if any value differs. The load-transient tasks stay above
715 mV, so their `sensor1` columns are saturated at 47 and the voltage comes
from `sensor0`; the DVS tasks use both channels.

## Reproducing the CSV files

```bash
pip install openpyxl
python scripts/export_csv.py          # rewrites data/csv/*.csv from the workbook
python scripts/export_csv.py --check  # verifies the workbook and the CSV files
```

Python 3.8 or newer; the script has no other dependency.

## License

The data (`data/`) is licensed under the Creative Commons Attribution 4.0
International License (`LICENSE`). When reusing it, credit "School of
Integrated Circuits, Peking University" and link to this repository. The
script (`scripts/`) is licensed under the Apache License 2.0
(`LICENSES/Apache-2.0.txt`).

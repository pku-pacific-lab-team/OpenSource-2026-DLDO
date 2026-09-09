#!/usr/bin/env python3
# Copyright 2026 School of Integrated Circuits, Peking University
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy of
# the License at http://www.apache.org/licenses/LICENSE-2.0 (a copy is in
# LICENSES/Apache-2.0.txt of this repository).
"""Split the sensor export workbook into one CSV file per measurement task.

Usage (from the repository root):

    python scripts/export_csv.py            # writes data/csv/*.csv and prints a summary
    python scripts/export_csv.py --check    # only verifies the workbook and the existing CSV files

The workbook `data/v_sensor_results.xlsx` holds the eight tasks side by side in
one sheet (`sensor_export`), separated by an empty column. Each task block has
the columns `t`, `sensor0_1..64`, `sensor1_1..64`, `vdd_measured_1..64`. The
script keeps the column names, verifies that `vdd_measured_*` equals the value
recovered from the two sensor codes, and names the CSV files after the tasks.
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parents[1]
XLSX = ROOT / "data" / "v_sensor_results.xlsx"
OUT = ROOT / "data" / "csv"

# Task order of the export (left to right in the sheet), file names and conditions.
TASKS = [
    ("01_load_slow_vdn", "load step 144 -> 1004 mA, 20 ns edge, 800 mV output"),
    ("02_load_slow_vup", "load step 1004 -> 144 mA, 20 ns edge, 800 mV output"),
    ("03_load_fast_vdn", "load step 144 -> 573 mA, 0.2 ns edge, 800 mV output"),
    ("04_load_fast_vup", "load step 573 -> 144 mA, 0.2 ns edge, 800 mV output"),
    ("05_dvs_down_boosting", "DVS 800 -> 600 mV with DVS repair and boosting"),
    ("06_dvs_down_repair", "DVS 800 -> 600 mV with DVS repair only"),
    ("07_dvs_up_boosting", "DVS 600 -> 800 mV with DVS repair and boosting"),
    ("08_dvs_up_repair", "DVS 600 -> 800 mV with DVS repair only"),
]
RUNS = 64


def recover(sensor0: int, sensor1: int) -> int:
    """Voltage in mV from the two 6-bit sensor codes (see README)."""
    return 600 + 5 * (sensor1 - 24) if sensor1 < 47 else 800 + 5 * (sensor0 - 24)


def load_blocks() -> list[tuple[list[str], list[list]]]:
    ws = openpyxl.load_workbook(XLSX, read_only=True, data_only=True)["sensor_export"]
    rows = [list(r) for r in ws.iter_rows(values_only=True)]
    header = [("" if h is None else str(h)) for h in rows[0]]
    starts = [i for i, h in enumerate(header) if h == "t"]
    if len(starts) != len(TASKS):
        sys.exit(f"expected {len(TASKS)} task blocks, found {len(starts)}")
    blocks = []
    for k, start in enumerate(starts):
        end = starts[k + 1] - 1 if k + 1 < len(starts) else len(header)
        names = header[start:end]
        expect = ["t"] + [f"sensor0_{i}" for i in range(1, RUNS + 1)] + [f"sensor1_{i}" for i in range(1, RUNS + 1)] \
            + [f"vdd_measured_{i}" for i in range(1, RUNS + 1)]
        if names != expect:
            sys.exit(f"block {k + 1}: unexpected column names")
        data = [r[start:end] for r in rows[1:] if r[start] is not None]
        blocks.append((names, data))
    return blocks


def verify(k: int, names: list[str], data: list[list]) -> dict:
    """Check the time grid and the voltage recovery; return summary numbers."""
    t = [float(r[0]) for r in data]
    steps = {round(b - a, 6) for a, b in zip(t, t[1:])}
    if steps != {0.5}:
        sys.exit(f"block {k + 1}: time grid is not 0.5 ns ({sorted(steps)})")
    empty = 0
    s0 = []
    s1 = []
    v = []
    for r in data:
        for i in range(RUNS):
            a, b, c = r[1 + i], r[1 + RUNS + i], r[1 + 2 * RUNS + i]
            if a is None or b is None or c is None:
                empty += 1
                continue
            a, b, c = int(a), int(b), int(c)
            if recover(a, b) != c:
                sys.exit(f"block {k + 1}: vdd_measured_{i + 1} at t={r[0]} does not match the recovery formula")
            s0.append(a)
            s1.append(b)
            v.append(c)
    return dict(rows=len(data), t_min=min(t), t_max=max(t), s0=(min(s0), max(s0)), s1=(min(s1), max(s1)),
                v=(min(v), max(v)), empty=empty)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="verify only, do not write CSV files")
    args = ap.parse_args()
    blocks = load_blocks()
    OUT.mkdir(parents=True, exist_ok=True)
    print(f"{'file':26s} {'rows':>5s} {'t range (ns)':>14s} {'sensor0':>8s} {'sensor1':>8s} {'vdd (mV)':>10s} {'empty':>6s}")
    for k, ((names, data), (name, _)) in enumerate(zip(blocks, TASKS)):
        s = verify(k, names, data)
        path = OUT / f"{name}.csv"
        if args.check:
            with path.open(encoding="utf-8", newline="") as fh:
                got = [row for row in csv.reader(fh)]
            want = [names] + [["" if v is None else (str(int(v)) if float(v).is_integer() else str(v)) for v in r] for r in data]
            if got != want:
                sys.exit(f"{path.name} differs from the workbook")
        else:
            with path.open("w", encoding="utf-8", newline="") as fh:
                w = csv.writer(fh, lineterminator="\n")
                w.writerow(names)
                for r in data:
                    w.writerow(["" if v is None else (int(v) if float(v).is_integer() else v) for v in r])
        print(f"{path.name:26s} {s['rows']:5d} {s['t_min']:6.1f}..{s['t_max']:5.1f} "
              f"{s['s0'][0]:3d}-{s['s0'][1]:<3d} {s['s1'][0]:4d}-{s['s1'][1]:<3d} {s['v'][0]:5d}-{s['v'][1]:<4d} {s['empty']:6d}")
    print("verified" if args.check else f"written to {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

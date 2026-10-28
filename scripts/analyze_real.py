#!/usr/bin/env python3
"""Robust summary of a real-I/O run: outlier flags and paired comparisons.

    python scripts/analyze_real.py results/real/<label>/runs.csv --out analysis.md
    python scripts/analyze_real.py console_log.txt --out analysis.md     # also reads the console log

Why: a shared machine occasionally stalls the drive (a run can take 2-3x longer
than its siblings). With three repeats a median hides one stall, but then ratios
between cells are computed from mixed-quality numbers. This script
  * flags a run as disturbed if it took more than 1.3x the fastest run of the same cell,
  * reports the median of the undisturbed runs,
  * compares each configuration with the baseline repeat by repeat (configurations are
    shuffled within a repeat, so a repeat is the fairest pairing), using only repeats where
    both runs were undisturbed, and counts in how many of them it was faster.
"""

from __future__ import annotations

import argparse
import csv
import re
from collections import defaultdict
from statistics import median

DISTURBED = 1.3


def load(path: str):
    """Return {(workload, config): {repeat: seconds}}."""
    data = defaultdict(dict)
    if path.endswith(".csv"):
        for r in csv.DictReader(open(path)):
            data[(r["workload"], r["config"])][int(r["repeat"])] = float(r["total_ms"]) / 1e3
        return data
    wl = None
    for line in open(path):
        m = re.match(r"\[(\w+)\] writing", line)
        if m:
            wl = m.group(1)
            continue
        m = re.match(r"\s+rep (\d+) (\S+)\s+([\d.]+) s", line)
        if m and wl:
            data[(wl, m.group(2))][int(m.group(1))] = float(m.group(3))
    return data


def cells(data):
    """Per workload and configuration: times, undisturbed times, and the workloads in order."""
    workloads = list(dict.fromkeys(w for w, _ in data))
    out = {}
    for w in workloads:
        group = {c: t for (ww, c), t in data.items() if ww == w}
        for c, t in group.items():
            lo = min(t.values())
            out[(w, c)] = (t, {rep: s for rep, s in t.items() if s <= DISTURBED * lo})
    return workloads, out


def speedups(data, baseline: str):
    """{(workload, config): dict(speedup, wins, pairs, disturbed, clean_median, times)}."""
    workloads, grid = cells(data)
    res = {}
    for (w, c), (t, clean) in grid.items():
        base = grid.get((w, baseline), ({}, {}))[1]
        pairs = [base[r] / clean[r] for r in clean if r in base]
        res[(w, c)] = dict(
            speedup=None if c == baseline or not pairs else median(pairs),
            wins=sum(p > 1 for p in pairs), pairs=len(pairs), disturbed=len(t) - len(clean),
            clean_median=median(clean.values()), times=t, clean=set(clean),
        )
    return res


def analyse(data, baseline: str):
    res = speedups(data, baseline)
    workloads = list(dict.fromkeys(w for w, _ in data))
    out = []
    for w in workloads:
        out += ["", f"## {w}", "",
                f"Paired against `{baseline}`, repeat by repeat. `speedup` = baseline time / config time over repeats where both ran undisturbed.",
                "", "| config | times (s) | disturbed runs | median of clean runs (s) | speedup vs " + baseline + " | faster in |",
                "| --- | --- | ---: | ---: | ---: | ---: |"]
        for (ww, c), r in res.items():
            if ww != w:
                continue
            times = ", ".join(f"{r['times'][k]:.1f}" + ("*" if k not in r["clean"] else "") for k in sorted(r["times"]))
            sp = "-" if r["speedup"] is None else f"{r['speedup']:.2f}x"
            wins = "-" if r["speedup"] is None else f"{r['wins']} of {r['pairs']}"
            out.append(f"| {c} | {times} | {r['disturbed']} | {r['clean_median']:.2f} | {sp} | {wins} |")
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path")
    ap.add_argument("--baseline", default="lru")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    text = ("# Robust analysis (paired by repeat; `*` = disturbed run, excluded)\n" + analyse(load(a.path), a.baseline) + "\n")
    if a.out:
        open(a.out, "w").write(text)
    print(text)


if __name__ == "__main__":
    main()

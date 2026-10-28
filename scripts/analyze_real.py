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


def analyse(data, baseline: str):
    workloads = list(dict.fromkeys(w for w, _ in data))
    out = []
    for w in workloads:
        cells = {c: t for (ww, c), t in data.items() if ww == w}
        clean = {}
        for c, t in cells.items():
            lo = min(t.values())
            clean[c] = {rep: s for rep, s in t.items() if s <= DISTURBED * lo}
        out += ["", f"## {w}", "",
                f"Paired against `{baseline}`, repeat by repeat. `speedup` = baseline time / config time over repeats where both ran undisturbed.",
                "", "| config | times (s) | disturbed runs | median of clean runs (s) | speedup vs " + baseline + " | faster in |",
                "| --- | --- | ---: | ---: | ---: | ---: |"]
        base = clean.get(baseline, {})
        for c, t in cells.items():
            times = ", ".join(f"{t[r]:.1f}" + ("*" if r not in clean[c] else "") for r in sorted(t))
            bad = len(t) - len(clean[c])
            med = median(clean[c].values())
            pairs = [base[r] / clean[c][r] for r in clean[c] if r in base]
            if c == baseline or not pairs:
                sp, wins = "-", "-"
            else:
                sp = f"{median(pairs):.2f}x"
                wins = f"{sum(p > 1 for p in pairs)} of {len(pairs)}"
            out.append(f"| {c} | {times} | {bad} | {med:.2f} | {sp} | {wins} |")
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

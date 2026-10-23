#!/usr/bin/env python3
"""Turn measured results into the paper's figures and LaTeX tables.

    python scripts/make_paper_artifacts.py

Reads results/content/{compression,ablation}.csv and results/runs_*.csv and
writes paper/figures/*.pdf and paper/generated/*.tex. The paper \\input's these
fragments, so its numbers cannot drift from the results files.
"""

from __future__ import annotations

import csv
import os
import sys
from statistics import median

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from augur.network.breakeven import (  # noqa: E402
    CodecProfile, Bps_to_mbit, break_even_bandwidth, coded_time, fastest, mbit_to_Bps, raw_time,
)

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
RES = os.path.join(ROOT, "results")
FIG = os.path.join(ROOT, "paper", "figures")
GEN = os.path.join(ROOT, "paper", "generated")
os.makedirs(FIG, exist_ok=True)
os.makedirs(GEN, exist_ok=True)

CODECS = ["gzip-9", "bzip2-9", "xz-9e", "zstd-19", "brotli-11", "augur-cm"]
# Categorical slots 1-6 of the validated reference palette, fixed order; shape is the secondary encoding.
COLOR = dict(zip(CODECS, ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]))
MARK = dict(zip(CODECS, ["o", "s", "^", "D", "v", "P"]))
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e3e2de"
INCOMPRESSIBLE = ["precompressed_gzip", "precompressed_jpeg", "random_control"]
LABEL = {
    "source_code": "source code", "prose_docs": "prose (docs)", "system_log": "system log",
    "json_metadata": "JSON", "executable_elf": "executable (ELF)", "dna_bacterial": "DNA, bacterial",
    "dna_viral": "DNA, viral", "precompressed_gzip": "gzip file", "precompressed_jpeg": "JPEG image",
    "random_control": "random bytes",
}

plt.rcParams.update({
    "font.family": "serif", "font.serif": ["Liberation Serif", "Times New Roman", "DejaVu Serif"],
    "font.size": 7.5, "axes.labelsize": 7.5, "xtick.labelsize": 7, "ytick.labelsize": 7,
    "legend.fontsize": 6.5, "axes.edgecolor": INK2, "axes.labelcolor": INK, "text.color": INK,
    "xtick.color": INK2, "ytick.color": INK2, "pdf.fonttype": 42, "axes.linewidth": 0.6,
})


def tex(s: str) -> str:
    return s.replace("_", r"\_")


def spct(x: float, digits: int = 1) -> str:
    """Signed percentage for LaTeX with a true minus sign."""
    sign = "$-$" if x < 0 else "+"
    return f"{sign}{abs(x):.{digits}f}\\%"


def vtex(name: str) -> str:
    return tex(name).replace("<=", r"$\leq$")


def mbps(v: float) -> str:
    return f"{v:.0f}" if v >= 100 else (f"{v:.1f}" if v >= 10 else f"{v:.2f}")


def load(path):
    with open(path) as fh:
        return list(csv.DictReader(fh))


rows = load(os.path.join(RES, "content", "compression.csv"))
for r in rows:
    for k in ("bytes", "compressed", "bpb", "ratio", "compress_MBps", "decompress_MBps"):
        r[k] = float(r[k])
by = {(r["file"], r["codec"]): r for r in rows}
files = list(dict.fromkeys(r["file"] for r in rows))
compressible = [f for f in files if f not in INCOMPRESSIBLE]


def write(name: str, text: str) -> None:
    with open(os.path.join(GEN, name), "w") as fh:
        fh.write(text)


# ---------------------------------------------------------------- Table: bits per byte
classical = [c for c in CODECS if c != "augur-cm"]
lines = [r"\begin{tabular}{@{}lrrrrr@{}}", r"\toprule",
         r"File & xz-9e & zstd-19 & brotli-11 & augur-cm & $\Delta$ size \\", r"\midrule"]
gains = {}
for f in compressible + INCOMPRESSIBLE:
    best_classical = min(by[(f, c)]["bpb"] for c in classical)
    a = by[(f, "augur-cm")]["bpb"]
    gain = (a - best_classical) / best_classical * 100  # negative = smaller than the best classical codec
    gains[f] = gain
    def cell(c):
        v = by[(f, c)]["bpb"]
        txt = f"{v:.3f}"
        return rf"\textbf{{{txt}}}" if v == min(by[(f, k)]["bpb"] for k in CODECS) else txt
    lines.append(f"{LABEL[f]} & " + " & ".join(cell(c) for c in ["xz-9e", "zstd-19", "brotli-11", "augur-cm"])
                 + (f" & {spct(gain)} \\\\" if f in compressible else r" & -- \\"))
    if f == compressible[-1]:
        lines.append(r"\midrule")
lines += [r"\bottomrule", r"\end{tabular}"]
write("tab_bpb.tex", "\n".join(lines) + "\n")

# ---------------------------------------------------------------- Table: speed summary
lines = [r"\begin{tabular}{@{}lrrr@{}}", r"\toprule",
         r"Codec & bits/byte & comp.\ MB/s & decomp.\ MB/s \\", r"\midrule"]
for c in CODECS:
    lines.append(f"{c} & {median(by[(f, c)]['bpb'] for f in compressible):.3f} & "
                 f"{mbps(median(by[(f, c)]['compress_MBps'] for f in compressible))} & "
                 f"{mbps(median(by[(f, c)]['decompress_MBps'] for f in compressible))} \\\\")
lines += [r"\bottomrule", r"\end{tabular}"]
write("tab_speed.tex", "\n".join(lines) + "\n")

# ---------------------------------------------------------------- Break-even
profiles = {f: {c: CodecProfile(c, by[(f, c)]["ratio"], by[(f, c)]["compress_MBps"] * 1e6,
                                by[(f, c)]["decompress_MBps"] * 1e6) for c in CODECS} for f in files}
be_files = [f for f in compressible if f != "dna_viral"]  # 30 kB: throughput dominated by fixed set-up cost
lines = [r"\begin{tabular}{@{}lrrr@{}}", r"\toprule",
         r"File & static & sequential & pipelined \\", r"\midrule"]
md = ["# Break-even bandwidth of augur-cm versus sending raw (Mbit/s)", "",
      "Coding is faster than raw below this bandwidth. Derived from measured ratio and throughput.", "",
      "| file | static | sequential | pipelined |", "| --- | ---: | ---: | ---: |"]
for f in be_files:
    p = profiles[f]["augur-cm"]
    vals = [Bps_to_mbit(break_even_bandwidth(p, s)) for s in ("static", "sequential", "pipelined")]
    lines.append(f"{LABEL[f]} & " + " & ".join(f"{v:.2f}" for v in vals) + r" \\")
    md.append(f"| {f} | " + " | ".join(f"{v:.2f}" for v in vals) + " |")
lines += [r"\bottomrule", r"\end{tabular}"]
write("tab_breakeven.tex", "\n".join(lines) + "\n")

BWS = [0.5, 2, 10, 50, 250]
lines = [r"\begin{tabular}{@{}l" + "r" * len(BWS) + r"@{}}", r"\toprule",
         "File & " + " & ".join(f"{b:g}" for b in BWS) + r" \\", r"\midrule"]
md += ["", "# Fastest option by link speed (static scenario, 1 MiB file)", "",
       "| file | " + " | ".join(f"{b:g} Mbit/s" for b in BWS) + " |", "| --- | " + " | ".join("---" for _ in BWS) + " |"]
for f in be_files:
    size = by[(f, "xz-9e")]["bytes"]
    cells = [fastest(size, profiles[f].values(), mbit_to_Bps(b), "static") for b in BWS]
    lines.append(f"{LABEL[f]} & " + " & ".join(tex(c) for c in cells) + r" \\")
    md.append(f"| {f} | " + " | ".join(cells) + " |")
lines += [r"\bottomrule", r"\end{tabular}"]
write("tab_winner.tex", "\n".join(lines) + "\n")
with open(os.path.join(RES, "content", "breakeven.md"), "w") as fh:
    fh.write("\n".join(md) + "\n")

# ---------------------------------------------------------------- Crossover vs the classical codecs
def crossover_mbit(f: str):
    """Highest bandwidth (Mbit/s) at which augur-cm is still the fastest option, static scenario."""
    size = by[(f, "xz-9e")]["bytes"]
    best = None
    for k in range(-400, 601):  # 1e-4 .. 1e6 Mbit/s on a log grid
        b = 10 ** (k / 100)
        if fastest(size, profiles[f].values(), mbit_to_Bps(b), "static") == "augur-cm":
            best = b
    return best


def required_speedup(f: str, mbit: float) -> float:
    """Factor by which augur-cm's decompression must speed up to be the fastest option at this bandwidth."""
    a = profiles[f]["augur-cm"]
    B = mbit_to_Bps(mbit)
    # time per byte for each classical codec (static): ratio/B + 1/decompress
    t_best = min(c.ratio / B + 1.0 / c.decompress_Bps for k, c in profiles[f].items() if k != "augur-cm")
    budget = t_best - a.ratio / B  # seconds per byte left for decompression
    if budget <= 0:
        return float("inf")
    return (1.0 / budget) / a.decompress_Bps


lines = [r"\begin{tabular}{@{}lrrrr@{}}", r"\toprule",
         r"File & fastest below & \multicolumn{3}{c}{speed-up needed at (Mbit/s)} \\",
         r"\cmidrule(l){3-5}", r" & (Mbit/s) & 2 & 10 & 50 \\", r"\midrule"]
md += ["", "# Where does augur-cm win on time? (static scenario)", "",
       "| file | fastest below (Mbit/s) | speed-up needed at 2 | at 10 | at 50 |", "| --- | ---: | ---: | ---: | ---: |"]
for f in be_files:
    x = crossover_mbit(f)
    xs = f"{x:.2g}" if x else "never"
    req = [required_speedup(f, b) for b in (2, 10, 50)]
    rs = [("--" if r == float("inf") else f"{r:.0f}$\\times$") for r in req]
    lines.append(f"{LABEL[f]} & {xs} & " + " & ".join(rs) + r" \\")
    md.append(f"| {f} | {xs} | " + " | ".join("inf" if r == float("inf") else f"{r:.0f}x" for r in req) + " |")
lines += [r"\bottomrule", r"\end{tabular}"]
write("tab_crossover.tex", "\n".join(lines) + "\n")
with open(os.path.join(RES, "content", "breakeven.md"), "w") as fh:
    fh.write("\n".join(md) + "\n")

# ---------------------------------------------------------------- Fig 1: bits per byte, dot plot
order = sorted(compressible, key=lambda f: by[(f, "augur-cm")]["bpb"])
fig, ax = plt.subplots(figsize=(3.45, 2.75))
for i, f in enumerate(order):
    ax.axhline(i, color=GRID, lw=0.5, zorder=0)
    for c in CODECS:
        ax.plot(by[(f, c)]["bpb"], i + (CODECS.index(c) - 2.5) * 0.085, MARK[c], color=COLOR[c], ms=5.5 if c == "augur-cm" else 4.2,
                mec="#fcfcfb", mew=0.6, zorder=3 if c == "augur-cm" else 2, label=c if i == 0 else None)
ax.set_yticks(range(len(order)))
ax.set_yticklabels([LABEL[f] for f in order])
ax.set_xlabel("compressed bits per input byte (lower is better)")
ax.set_xlim(0, 3.1)
ax.invert_yaxis()
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
ax.legend(ncol=3, loc="lower center", bbox_to_anchor=(0.45, 1.0), frameon=False, handletextpad=0.2,
          columnspacing=0.8, borderaxespad=0.2)
fig.tight_layout(pad=0.3)
fig.savefig(os.path.join(FIG, "fig_bpb.pdf"))
plt.close(fig)

# ---------------------------------------------------------------- Fig 2: time versus bandwidth
f2 = "source_code"
size = by[(f2, "xz-9e")]["bytes"]
bw = [10 ** (x / 20) for x in range(-40, 61)]  # 0.01 .. 1000 Mbit/s
fig, ax = plt.subplots(figsize=(3.45, 2.45))
ax.plot(bw, [raw_time(size, mbit_to_Bps(b)) for b in bw], color=INK, lw=1.2, ls=(0, (4, 2)), label="raw")
for c in ["zstd-19", "xz-9e", "brotli-11", "augur-cm"]:
    ax.plot(bw, [coded_time(size, profiles[f2][c], mbit_to_Bps(b), "static") for b in bw], color=COLOR[c],
            lw=1.6 if c == "augur-cm" else 1.0, label=c)
ax.set_xscale("log")
ax.set_yscale("log")
ax.set_xlabel("link bandwidth (Mbit/s)")
ax.set_ylabel("time to deliver 1 MiB of source code (s)")
ax.grid(True, color=GRID, lw=0.5, which="major")
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
ax.legend(frameon=False, loc="lower left")
fig.tight_layout(pad=0.3)
fig.savefig(os.path.join(FIG, "fig_time.pdf"))
plt.close(fig)

# ---------------------------------------------------------------- Ablation table
abl_path = os.path.join(RES, "content", "ablation.csv")
if os.path.exists(abl_path):
    ab = load(abl_path)
    for r in ab:
        r["bpb"] = float(r["bpb"])
        r["compress_MBps"] = float(r["compress_MBps"])
    abby = {(r["file"], r["variant"]): r for r in ab}
    variants = list(dict.fromkeys(r["variant"] for r in ab))
    afiles = [f for f in ["source_code", "prose_docs", "system_log", "json_metadata", "executable_elf", "dna_bacterial"]
              if (f, "full") in abby]
    lines = [r"\begin{tabular}{@{}l" + "r" * (len(afiles) + 1) + r"@{}}", r"\toprule",
             "Variant & " + " & ".join(LABEL[f] for f in afiles) + r" & MB/s \\", r"\midrule"]
    for v in variants:
        cells = []
        for f in afiles:
            base = abby[(f, "full")]["bpb"]
            val = abby[(f, v)]["bpb"]
            cells.append(f"{val:.3f}" if v == "full" else f"{val:.3f} ({spct((val - base) / base * 100)})")
        sp = median(abby[(f, v)]["compress_MBps"] for f in afiles)
        lines.append(f"{vtex(v)} & " + " & ".join(cells) + f" & {mbps(sp)} \\\\")
        if v == "full":
            lines.append(r"\midrule")
    lines += [r"\bottomrule", r"\end{tabular}"]
    write("tab_ablation.tex", "\n".join(lines) + "\n")

# ---------------------------------------------------------------- Storage simulation table
def storage_table():
    path = os.path.join(RES, "runs_sata_ssd.csv")
    if not os.path.exists(path):
        return
    data = load(path)
    wl = list(dict.fromkeys(r["workload"] for r in data))
    cfgs = ["sequential", "stride", "markov2", "markov2+gate", "markov2-naive", "oracle"]
    lines = [r"\begin{tabular}{@{}l" + "r" * len(cfgs) + r"@{}}", r"\toprule",
             "Workload & " + " & ".join(tex(c) for c in cfgs) + r" \\", r"\midrule"]
    names = {"sequential": "sequential", "random": "random", "zipf_workingset": "Zipf working set",
             "phased": "phased", "recurring_routines": "recurring routines",
             "dl_reshuffled": "DL, reshuffled", "dl_fixed_order": "DL, fixed order"}
    for w in wl:
        cells = []
        for c in cfgs:
            v = median(float(r["speedup_vs_lru"]) for r in data if r["workload"] == w and r["config"] == c)
            cells.append(f"{v:.2f}")
        lines.append(f"{names.get(w, tex(w))} & " + " & ".join(cells) + r" \\")
    lines += [r"\bottomrule", r"\end{tabular}"]
    write("tab_storage.tex", "\n".join(lines) + "\n")


storage_table()
print("wrote", sorted(os.listdir(GEN)), sorted(os.listdir(FIG)))
print({LABEL[f]: round(g, 1) for f, g in gains.items() if f in compressible})

#!/usr/bin/env python3
"""Sanity-check the baselines used in the content benchmark.

    python scripts/check_baselines.py --corpus data/test --out results/content

1. Wrapper check: compressed sizes from the Python bindings must match the
   command-line tools (gzip -9, bzip2 -9, xz -9e) to within a few header bytes.
2. Headroom check: would stronger settings of zstd and brotli narrow the gap to
   augur-cm? (zstd level 22 with a long window, brotli with each text mode.)
3. Context: order-0 empirical entropy of every file, a loose reference point.

Writes results/content/baseline_check.md.
"""

from __future__ import annotations

import argparse
import glob
import gzip
import math
import os
import shutil
import subprocess
import sys
from collections import Counter

import brotli
import zstandard

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import bz2  # noqa: E402
import lzma  # noqa: E402


def cli_size(cmd, data: bytes):
    if shutil.which(cmd[0]) is None:
        return None
    return len(subprocess.run(cmd, input=data, capture_output=True, check=True).stdout)


def order0_bpb(data: bytes) -> float:
    n = len(data)
    return -sum(c / n * math.log2(c / n) for c in Counter(data).values())


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--corpus", default="data/test")
    ap.add_argument("--out", default="results/content")
    args = ap.parse_args()

    out = ["# Baseline check (measured)", "",
           "## 1. Python bindings versus command-line tools (compressed bytes)", "",
           "| file | gzip lib | gzip CLI | bzip2 lib | bzip2 CLI | xz lib | xz CLI |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    head2 = ["", "## 2. Stronger baseline settings (bits per byte)", "",
             "| file | zstd-19 | zstd-22 long | brotli-11 generic | brotli-11 text | best baseline | augur-cm |",
             "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"]
    head3 = ["", "## 3. Order-0 empirical entropy (bits per byte)", "", "| file | order-0 entropy | best baseline | augur-cm |",
             "| --- | ---: | ---: | ---: |"]
    import csv
    res = {(r["file"], r["codec"]): float(r["bpb"]) for r in csv.DictReader(open(os.path.join(args.out, "compression.csv")))}
    worst = 0
    for path in sorted(glob.glob(os.path.join(args.corpus, "*.bin"))):
        name = os.path.basename(path)[:-4]
        d = open(path, "rb").read()
        n = len(d)
        g, b, x = len(gzip.compress(d, 9, mtime=0)), len(bz2.compress(d, 9)), len(lzma.compress(d, preset=9 | lzma.PRESET_EXTREME))
        gc = cli_size(["gzip", "-9", "-n", "-c"], d)
        bc = cli_size(["bzip2", "-9", "-c"], d)
        xc = cli_size(["xz", "-9e", "-c"], d)
        for lib, cli in ((g, gc), (b, bc), (x, xc)):
            if cli is not None:
                worst = max(worst, abs(lib - cli))
        out.append(f"| {name} | {g} | {gc} | {b} | {bc} | {x} | {xc} |")
        z19 = 8 * len(zstandard.ZstdCompressor(level=19).compress(d)) / n
        z22 = 8 * len(zstandard.ZstdCompressor(compression_params=zstandard.ZstdCompressionParameters.from_level(22, window_log=27)).compress(d)) / n
        bg = 8 * len(brotli.compress(d, quality=11, lgwin=24, mode=brotli.MODE_GENERIC)) / n
        bt = 8 * len(brotli.compress(d, quality=11, lgwin=24, mode=brotli.MODE_TEXT)) / n
        best = min(res[(name, c)] for c in ["gzip-9", "bzip2-9", "xz-9e", "zstd-19", "brotli-11"])
        best_any = min(best, z22, bg, bt)
        head2.append(f"| {name} | {z19:.3f} | {z22:.3f} | {bg:.3f} | {bt:.3f} | {best_any:.3f} | {res[(name, 'augur-cm')]:.3f} |")
        head3.append(f"| {name} | {order0_bpb(d):.3f} | {best_any:.3f} | {res[(name, 'augur-cm')]:.3f} |")
    out.append("")
    out.append(f"Largest size difference between a Python binding and its CLI: {worst} bytes.")
    text = "\n".join(out + head2 + head3) + "\n"
    with open(os.path.join(args.out, "baseline_check.md"), "w") as fh:
        fh.write(text)
    print(text)


if __name__ == "__main__":
    main()

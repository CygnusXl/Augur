"""Ablations of the predictive codec: which parts of the model earn their cost?

    python -m augur.content.ablate --corpus data/test --out results/content

Each variant is the same C source compiled with different switches
(``AUGUR_ORDER_MASK``, ``AUGUR_NO_MATCH``, ``AUGUR_TABLE_BITS``). Orders are
{1,2,3,4,5,6,8,12} bytes of context; the mask bit i enables the i-th of them.
Every variant is verified to decode exactly. Sizes use the bare model stream
(no stored-mode fallback) so that the model itself is what is compared.
"""

from __future__ import annotations

import argparse
import csv
import glob
import hashlib
import os
import time
from typing import Dict, List

from .codec import AugurCM

VARIANTS: Dict[str, Dict[str, int]] = {
    "full": {},
    "no-match-model": {"AUGUR_NO_MATCH": 1},
    "orders<=4": {"AUGUR_ORDER_MASK": 0b00001111},
    "orders<=6": {"AUGUR_ORDER_MASK": 0b00111111},
    "no-order-8,12": {"AUGUR_ORDER_MASK": 0b00111111},
    "order-2-only": {"AUGUR_ORDER_MASK": 0b00000010},
    "table-bits=16": {"AUGUR_TABLE_BITS": 16},
    "table-bits=18": {"AUGUR_TABLE_BITS": 18},
    "table-bits=20": {"AUGUR_TABLE_BITS": 20},
    "table-bits=24": {"AUGUR_TABLE_BITS": 24},
}
# "orders<=6" and "no-order-8,12" are the same switch; keep one.
del VARIANTS["no-order-8,12"]
FILES = ["source_code", "prose_docs", "system_log", "json_metadata", "executable_elf", "dna_bacterial", "dna_viral"]


def main(argv: List[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--corpus", default="data/test")
    p.add_argument("--out", default="results/content")
    args = p.parse_args(argv)
    rows = []
    for f in FILES:
        path = os.path.join(args.corpus, f + ".bin")
        if not os.path.exists(path):
            continue
        data = open(path, "rb").read()
        for vname, defs in VARIANTS.items():
            c = AugurCM(**defs)
            t0 = time.perf_counter()
            blob = c.compress_raw(data)
            t_c = time.perf_counter() - t0
            ok = c.decompress(bytes([1]) + blob) == data
            assert ok, (f, vname)
            rows.append({"file": f, "variant": vname, "bytes": len(data), "compressed": len(blob),
                         "bpb": 8 * len(blob) / len(data), "compress_MBps": len(data) / t_c / 1e6})
            print(f"{f:16s} {vname:16s} {8*len(blob)/len(data):6.3f} bpb  {len(data)/t_c/1e6:6.2f} MB/s", flush=True)
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "ablation.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    names = list(VARIANTS)
    by = {(r["file"], r["variant"]): r for r in rows}
    files = [f for f in FILES if (f, "full") in by]
    lines = ["# Ablation of the predictive codec (measured)", "",
             "Bits per byte; every variant decoded exactly.", "",
             "| file | " + " | ".join(names) + " |", "| --- | " + " | ".join("---:" for _ in names) + " |"]
    for f in files:
        lines.append(f"| {f} | " + " | ".join(f"{by[(f, n)]['bpb']:.3f}" for n in names) + " |")
    lines += ["", "Compress throughput (MB/s):", "", "| file | " + " | ".join(names) + " |",
              "| --- | " + " | ".join("---:" for _ in names) + " |"]
    for f in files:
        lines.append(f"| {f} | " + " | ".join(f"{by[(f, n)]['compress_MBps']:.2f}" for n in names) + " |")
    with open(os.path.join(args.out, "ablation.md"), "w") as fh:
        fh.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()

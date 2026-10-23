"""Compression benchmark: general-purpose codecs versus the predictive codec.

    python scripts/build_corpus.py --out data
    python -m augur.content.bench --corpus data/test --out results/content

For every file and codec it records compressed size, bits per byte, compress
and decompress throughput (median of ``--repeats`` runs, wall clock, single
thread) and verifies that decompression returns the original bytes exactly
(SHA-256). A file that fails verification aborts the run.

Throughput is measured on whatever machine runs this; it is not portable.
"""

from __future__ import annotations

import argparse
import bz2
import csv
import glob
import gzip
import hashlib
import json
import lzma
import os
import platform
import time
from dataclasses import dataclass
from statistics import median
from typing import Callable, Dict, List

import brotli
import zstandard

from .codec import AugurCM


@dataclass(frozen=True)
class Codec:
    name: str
    compress: Callable[[bytes], bytes]
    decompress: Callable[[bytes], bytes]
    note: str = ""


def _zstd(level: int, long: bool = False) -> Codec:
    params = zstandard.ZstdCompressionParameters.from_level(level, window_log=27 if long else 0)
    return Codec(
        f"zstd-{level}",
        lambda d: zstandard.ZstdCompressor(compression_params=params).compress(d),
        lambda b: zstandard.ZstdDecompressor().decompress(b, max_output_size=1 << 30),
    )


def codecs(only: List[str] | None = None) -> Dict[str, Codec]:
    cm = AugurCM()
    table = [
        Codec("gzip-9", lambda d: gzip.compress(d, 9, mtime=0), gzip.decompress),
        Codec("bzip2-9", lambda d: bz2.compress(d, 9), bz2.decompress),
        Codec("xz-9e", lambda d: lzma.compress(d, preset=9 | lzma.PRESET_EXTREME), lzma.decompress),
        _zstd(19),
        Codec("brotli-11", lambda d: brotli.compress(d, quality=11, lgwin=24), brotli.decompress),
        Codec("augur-cm", cm.compress, cm.decompress, "predictive, exact"),
    ]
    return {c.name: c for c in table if not only or c.name in only}


def _time(fn: Callable[[], object], repeats: int):
    best = []
    out = None
    for _ in range(repeats):
        t0 = time.perf_counter()
        out = fn()
        best.append(time.perf_counter() - t0)
    return out, median(best)


def run(corpus: str, repeats: int, only: List[str] | None) -> List[Dict]:
    rows: List[Dict] = []
    for path in sorted(glob.glob(os.path.join(corpus, "*.bin"))):
        name = os.path.basename(path)[:-4]
        data = open(path, "rb").read()
        digest = hashlib.sha256(data).hexdigest()
        for cname, c in codecs(only).items():
            blob, t_c = _time(lambda: c.compress(data), repeats)
            back, t_d = _time(lambda: c.decompress(blob), repeats)
            if hashlib.sha256(back).hexdigest() != digest:
                raise SystemExit(f"ROUNDTRIP FAILURE: {cname} on {name}")
            n = len(data)
            rows.append({
                "file": name, "codec": cname, "bytes": n, "compressed": len(blob),
                "bpb": 8 * len(blob) / n, "ratio": len(blob) / n,
                "compress_MBps": n / t_c / 1e6, "decompress_MBps": n / t_d / 1e6,
                "verified": True,
            })
            print(f"{name:20s} {cname:10s} {len(blob):>9d}  {8*len(blob)/n:6.3f} bpb  "
                  f"c {n/t_c/1e6:7.2f}  d {n/t_d/1e6:7.2f} MB/s", flush=True)
    return rows


def markdown(rows: List[Dict], repeats: int) -> str:
    names = list(dict.fromkeys(r["codec"] for r in rows))
    files = list(dict.fromkeys(r["file"] for r in rows))
    by = {(r["file"], r["codec"]): r for r in rows}
    out = [
        "# Compression results (measured)",
        "",
        f"Machine: {platform.platform()}, {platform.processor() or platform.machine()}, "
        f"Python {platform.python_version()}. Median of {repeats} runs, single thread. "
        "Every output was decompressed and checked byte-for-byte against the input.",
        "",
        "## Bits per byte (lower is better; 8.00 = no compression)",
        "",
        "| file | bytes | " + " | ".join(names) + " |",
        "| --- | ---: | " + " | ".join("---:" for _ in names) + " |",
    ]
    for f in files:
        best = min(by[(f, c)]["bpb"] for c in names)
        cells = []
        for c in names:
            v = by[(f, c)]["bpb"]
            cells.append(f"**{v:.3f}**" if v == best else f"{v:.3f}")
        out.append(f"| {f} | {by[(f, names[0])]['bytes']} | " + " | ".join(cells) + " |")
    for key, title in (("compress_MBps", "Compress throughput (MB/s of input)"),
                       ("decompress_MBps", "Decompress throughput (MB/s of output)")):
        out += ["", f"## {title}", "", "| file | " + " | ".join(names) + " |",
                "| --- | " + " | ".join("---:" for _ in names) + " |"]
        for f in files:
            out.append(f"| {f} | " + " | ".join(f"{by[(f, c)][key]:.2f}" for c in names) + " |")
    return "\n".join(out) + "\n"


def main(argv: List[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--corpus", default="data/test")
    p.add_argument("--repeats", type=int, default=3)
    p.add_argument("--codecs", nargs="+", default=None)
    p.add_argument("--out", default="results/content")
    args = p.parse_args(argv)
    rows = run(args.corpus, args.repeats, args.codecs)
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "compression.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    md = markdown(rows, args.repeats)
    with open(os.path.join(args.out, "compression.md"), "w") as fh:
        fh.write(md)
    print(md)


if __name__ == "__main__":
    main()

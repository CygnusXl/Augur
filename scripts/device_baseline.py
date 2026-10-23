#!/usr/bin/env python3
"""Stage 1: measure cold vs warm read latency on YOUR drive.

Before any prefetching result means anything, the harness must be able to make
reads cold. This script writes a test file, evicts it from the page cache with
posix_fadvise(DONTNEED), and compares cold and warm reads. It also prints a
verdict on whether eviction appears to work.

    python scripts/device_baseline.py --dir /path/on/the/drive --size-mib 1024

Run it on the drive the benchmarks will use. Results from other machines say
nothing about yours. Linux only.
"""

from __future__ import annotations

import argparse
import os
import random
import statistics
import sys
import tempfile
import time

KiB = 1024
MiB = 1024 * KiB


def make_file(path: str, size_mib: int) -> None:
    with open(path, "wb") as fh:
        for _ in range(size_mib):
            fh.write(os.urandom(MiB))
        fh.flush()
        os.fsync(fh.fileno())


def evict(fd: int) -> None:
    os.fsync(fd)
    os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_DONTNEED)


def timed_reads(fd: int, offsets, size: int):
    lat = []
    t_all = time.perf_counter()
    for off in offsets:
        t0 = time.perf_counter()
        os.pread(fd, size, off)
        lat.append(time.perf_counter() - t0)
    return lat, time.perf_counter() - t_all


def describe(label: str, lat, wall: float, size: int) -> float:
    lat_us = sorted(x * 1e6 for x in lat)
    p99 = lat_us[min(len(lat_us) - 1, int(0.99 * len(lat_us)))]
    mb_s = len(lat) * size / wall / 1e6
    med = statistics.median(lat_us)
    print(f"{label:<22} median {med:9.1f} us   p99 {p99:9.1f} us   {mb_s:9.1f} MB/s")
    return med


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", default=tempfile.gettempdir(), help="directory on the drive to test")
    ap.add_argument("--size-mib", type=int, default=512)
    ap.add_argument("--block-kib", type=int, default=128)
    ap.add_argument("--reads", type=int, default=2000, help="random reads per pass")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    if not hasattr(os, "posix_fadvise"):
        print("posix_fadvise is not available on this platform (Linux required).")
        return 2

    path = os.path.join(args.dir, "augur_baseline.bin")
    size = args.block_kib * KiB
    n_blocks = args.size_mib * MiB // size
    rng = random.Random(args.seed)
    seq = [i * size for i in range(min(n_blocks, args.reads))]
    rnd = [rng.randrange(n_blocks) * size for _ in range(args.reads)]

    print(f"Writing {args.size_mib} MiB to {path} ...")
    make_file(path, args.size_mib)
    fd = os.open(path, os.O_RDONLY)
    try:
        results = {}
        for label, offs in (("sequential", seq), ("random", rnd)):
            evict(fd)
            cold, wall = timed_reads(fd, offs, size)
            results[(label, "cold")] = describe(f"{label} cold", cold, wall, size)
            warm, wall = timed_reads(fd, offs, size)
            results[(label, "warm")] = describe(f"{label} warm", warm, wall, size)
    finally:
        os.close(fd)
        os.remove(path)

    ratio = results[("random", "cold")] / max(results[("random", "warm")], 1e-9)
    print(f"\nRandom read, cold/warm median ratio: {ratio:.1f}x")
    if ratio < 1.5:
        print("WARNING: cold reads are not clearly slower than warm reads. Either the drive is very\n"
              "fast, the file system ignores the eviction hint (posix_fadvise is advisory), or the\n"
              "data stayed cached. Benchmark gains from prefetching cannot be trusted until this\n"
              "gap is real. Try a larger --size-mib, another file system, or O_DIRECT reads.")
        return 1
    print("OK: eviction appears to work, so cold-read benchmarks are meaningful on this drive.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

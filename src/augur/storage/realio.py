"""Real-I/O replay: the same traces and predictors, against a real file.

The simulator charges nominal device costs. This module instead performs the
reads with ``os.pread`` on a file you own, so latency is whatever your drive,
file system and kernel actually deliver.

Design choices that matter for honesty:

* Every run starts cold: the whole file is evicted from the page cache with
  ``posix_fadvise(DONTNEED)``. That call is advisory, so ``realbench``
  calibrates cold versus warm reads first and warns if the gap is not real.
* The kernel page cache would otherwise hold the whole (small) file after one
  pass, which hides the effect we want to measure. To emulate a dataset larger
  than RAM, each item is evicted from the page cache as soon as the application
  has it (application-cache configurations), or when it falls out of an LRU
  ledger of ``cache_bytes`` (OS-only configurations). Kernel readahead stays
  enabled unless a configuration turns it off. The ledger is an approximation:
  pages the kernel reads ahead outside any item stay cached until read.
* Application-cache and prefetch bookkeeping stays on the main thread. Worker
  threads only call ``pread``, so the cache needs no locks.
* Each item begins with its id, checked on every read, so a wrong offset or a
  short read fails loudly instead of being timed.
* Storage read volume comes from ``/proc/self/io`` (bytes the kernel really
  fetched from the device, readahead included), not from what the application
  asked for.

Linux only.
"""

from __future__ import annotations

import math
import os
import random
import struct
import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from statistics import median
from typing import Dict, List, Optional

from ..core.cache import ByteCache, Entry
from ..core.predictors import NoPredictor, Predictor
from ..core.scheduler import PrefetchScheduler, SchedulerConfig
from .traces import Trace

STAMP = struct.Struct("<Q")


# --------------------------------------------------------------------------
# data file
# --------------------------------------------------------------------------
class DataFile:
    """Items stored back to back in id order; item ``i`` starts with ``i`` as 8 bytes."""

    def __init__(self, path: str, sizes: Dict[int, int]):
        if any(s < STAMP.size for s in sizes.values()):
            raise ValueError("every item must be at least 8 bytes")
        self.path = path
        self.sizes = sizes
        self.offsets: Dict[int, int] = {}
        pos = 0
        for item in sorted(sizes):
            self.offsets[item] = pos
            pos += sizes[item]
        self.total_bytes = pos
        self.fd: Optional[int] = None

    def create(self, seed: int = 0) -> None:
        rng = random.Random(seed)
        with open(self.path, "wb") as fh:
            for item in sorted(self.sizes):
                fh.write(STAMP.pack(item))
                fh.write(rng.randbytes(self.sizes[item] - STAMP.size))
            fh.flush()
            os.fsync(fh.fileno())

    def open(self) -> None:
        self.fd = os.open(self.path, os.O_RDONLY)

    def close(self) -> None:
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None

    def remove(self) -> None:
        self.close()
        try:
            os.remove(self.path)
        except FileNotFoundError:
            pass

    def read(self, item: int) -> bytes:
        size = self.sizes[item]
        data = os.pread(self.fd, size, self.offsets[item])
        self.verify(item, data)
        return data

    def verify(self, item: int, data: bytes) -> None:
        if len(data) != self.sizes[item] or STAMP.unpack_from(data)[0] != item:
            raise RuntimeError(f"corrupt or short read for item {item}")

    def drop(self, item: int) -> None:
        """Ask the kernel to forget this item's pages."""
        os.posix_fadvise(self.fd, self.offsets[item], self.sizes[item], os.POSIX_FADV_DONTNEED)

    def evict_all(self) -> None:
        os.fsync(self.fd)
        os.posix_fadvise(self.fd, 0, 0, os.POSIX_FADV_DONTNEED)

    def set_readahead(self, enabled: bool) -> None:
        os.posix_fadvise(self.fd, 0, 0, os.POSIX_FADV_NORMAL if enabled else os.POSIX_FADV_RANDOM)


def calibrate(df: DataFile, n: int = 40, seed: int = 0) -> Dict[str, float]:
    """Cold versus warm random reads on this very file."""
    rng = random.Random(seed)
    items = [rng.choice(list(df.sizes)) for _ in range(n)]
    df.set_readahead(False)
    df.evict_all()

    def timed() -> float:
        out = []
        for it in items:
            t0 = time.perf_counter()
            df.read(it)
            out.append(time.perf_counter() - t0)
        return median(out)

    cold = timed()
    warm = timed()
    df.set_readahead(True)
    df.evict_all()
    return {"cold_us": cold * 1e6, "warm_us": warm * 1e6, "ratio": cold / max(warm, 1e-9)}


# --------------------------------------------------------------------------
# system probes (all best effort; None / NaN when unavailable)
# --------------------------------------------------------------------------
def read_bytes_from_device() -> float:
    try:
        with open("/proc/self/io") as fh:
            for line in fh:
                if line.startswith("read_bytes:"):
                    return float(line.split()[1])
    except OSError:
        pass
    return float("nan")


def _status_kb(field: str) -> float:
    try:
        with open("/proc/self/status") as fh:
            for line in fh:
                if line.startswith(field + ":"):
                    return float(line.split()[1])
    except OSError:
        pass
    return float("nan")


def reset_peak_rss() -> bool:
    try:
        with open("/proc/self/clear_refs", "w") as fh:
            fh.write("5")
        return True
    except OSError:
        return False


def fs_type(path: str) -> str:
    """File system type of the mount holding ``path`` (longest matching mount point)."""
    real = os.path.realpath(path)
    best, kind = "", "unknown"
    try:
        with open("/proc/mounts") as fh:
            for line in fh:
                parts = line.split()
                if len(parts) >= 3:
                    mp = parts[1].replace("\\040", " ")
                    if (real == mp or real.startswith(mp.rstrip("/") + "/")) and len(mp) > len(best):
                        best, kind = mp, parts[2]
    except OSError:
        pass
    return kind


def rotational(path: str) -> Optional[bool]:
    """True for a spinning disk, False for flash, None if unknown."""
    try:
        st = os.stat(path).st_dev
        base = os.path.realpath(f"/sys/dev/block/{os.major(st)}:{os.minor(st)}")
        for cand in (base, os.path.dirname(base)):
            f = os.path.join(cand, "queue", "rotational")
            if os.path.exists(f):
                return open(f).read().strip() == "1"
    except OSError:
        pass
    return None


def mem_total_mib() -> Optional[float]:
    try:
        with open("/proc/meminfo") as fh:
            for line in fh:
                if line.startswith("MemTotal:"):
                    return float(line.split()[1]) / 1024
    except OSError:
        pass
    return None


# --------------------------------------------------------------------------
# replay
# --------------------------------------------------------------------------
@dataclass
class RealConfig:
    cache_bytes: int
    policy: str = "lru"
    think_s: float = 1e-3
    workers: int = 4
    readahead: bool = True
    mode: str = "app"  # "app": application cache + optional prefetch; "os": no app cache
    # When the kernel is told to forget an item's pages: "immediate" = right after the application
    # has read it; "on_evict" = when the application cache evicts it (so the kernel and the
    # application hold the same items, and kernel readahead is left undisturbed in between).
    drop: str = "immediate"


def _pct(sorted_lat: List[float], p: float) -> float:
    n = len(sorted_lat)
    return sorted_lat[min(n - 1, max(0, math.ceil(p / 100.0 * n) - 1))]


def run_real(
    trace: Trace,
    df: DataFile,
    cfg: RealConfig,
    predictor: Optional[Predictor] = None,
    scheduler: Optional[PrefetchScheduler] = None,
) -> Dict[str, float]:
    predictor = predictor or NoPredictor()
    scheduler = scheduler or PrefetchScheduler(SchedulerConfig())
    sizes = trace.sizes
    depth = scheduler.cfg.depth
    nan = float("nan")
    c: Dict[str, float] = dict(
        hits=0, late_hits=0, misses=0, demand_bytes=0, prefetch_issued=0, prefetch_bytes=0,
        prefetch_useful=0, wasted_bytes=0, predictor_cpu_s=0.0,
    )

    df.set_readahead(cfg.readahead)
    df.evict_all()
    time.sleep(0.05)

    lazy = cfg.drop == "on_evict"

    def on_evict(key, entry: Entry) -> None:
        if lazy:
            df.drop(key)
        if entry.prefetched and not entry.used:
            c["wasted_bytes"] += entry.size
            scheduler.record_outcome(False)

    if cfg.mode == "os":
        # Bounded stand-in for a page cache: the ledger decides what we let the kernel keep.
        ledger = ByteCache(cfg.cache_bytes, "lru", on_evict=lambda k, e: df.drop(k))
        cache = None
    else:
        ledger = None
        cache = ByteCache(cfg.cache_bytes, cfg.policy, on_evict=on_evict)

    use_prefetch = cfg.mode == "app" and not isinstance(predictor, NoPredictor)
    executor = ThreadPoolExecutor(max_workers=cfg.workers) if use_prefetch else None
    inflight: Dict[int, Future] = {}
    inflight_bytes = 0

    def fetch(item: int) -> bytes:
        data = df.read(item)
        if not lazy:
            df.drop(item)  # the application owns this copy now; do not double-cache in the kernel
        return data

    def finalize() -> None:
        nonlocal inflight_bytes
        for item in [i for i, f in inflight.items() if f.done()]:
            fut = inflight.pop(item)
            inflight_bytes -= sizes[item]
            if not cache.put(item, sizes[item], fut.result(), prefetched=True):
                c["wasted_bytes"] += sizes[item]
                scheduler.record_outcome(False)
                if lazy:
                    df.drop(item)

    rss_reset = reset_peak_rss()
    rss0 = _status_kb("VmRSS")
    io0 = read_bytes_from_device()
    cpu0 = time.process_time()
    latencies: List[float] = []
    t_start = time.perf_counter()

    for item in trace.accesses:
        if cfg.think_s > 0:
            time.sleep(cfg.think_s)
        size = sizes[item]
        if cfg.mode == "os":
            t0 = time.perf_counter()
            df.read(item)
            latencies.append(time.perf_counter() - t0)
            if ledger.peek(item) is not None:
                ledger.get(item)
            elif not ledger.put(item, size):
                df.drop(item)
            continue

        if use_prefetch:
            finalize()
        t0 = time.perf_counter()
        entry = cache.peek(item)
        if entry is not None:
            first_use = entry.prefetched and not entry.used
            cache.get(item)
            c["hits"] += 1
            if first_use:
                c["prefetch_useful"] += 1
                scheduler.record_outcome(True)
        elif item in inflight:
            fut = inflight.pop(item)
            inflight_bytes -= size
            data = fut.result()
            cache.put(item, size, data, prefetched=True)
            cache.get(item)
            c["late_hits"] += 1
            c["prefetch_useful"] += 1
            scheduler.record_outcome(True)
        else:
            data = fetch(item)
            c["misses"] += 1
            c["demand_bytes"] += size
            if not cache.put(item, size, data, prefetched=False) and lazy:
                df.drop(item)
        latencies.append(time.perf_counter() - t0)

        if use_prefetch:
            t1 = time.perf_counter()
            predictor.observe(item)
            cands = predictor.predict(depth)
            c["predictor_cpu_s"] += time.perf_counter() - t1
            finalize()
            chosen = scheduler.select(
                cands, lambda i: i in cache, lambda i: i in inflight, sizes, len(inflight), inflight_bytes
            )
            for it in chosen:
                inflight[it] = executor.submit(fetch, it)
                inflight_bytes += sizes[it]
                c["prefetch_issued"] += 1
                c["prefetch_bytes"] += sizes[it]

    t_end = time.perf_counter()
    cpu_s = time.process_time() - cpu0
    peak_rss_kb = _status_kb("VmHWM")

    # Whatever was prefetched but never used is waste, including reads that finished late.
    if cache is not None:
        for fut in inflight.values():
            fut.result()
        for it in inflight:
            c["wasted_bytes"] += sizes[it]
        for _k, e in cache.entries():
            if e.prefetched and not e.used:
                c["wasted_bytes"] += e.size
    if executor is not None:
        executor.shutdown(wait=True)
    io1 = read_bytes_from_device()

    n = len(latencies)
    lat = sorted(latencies)
    wall = t_end - t_start
    issued = c["prefetch_issued"]
    app = cfg.mode == "app"
    return {
        "n": n,
        "mean_us": sum(lat) / n * 1e6,
        "median_us": median(lat) * 1e6,
        "p95_us": _pct(lat, 95) * 1e6,
        "p99_us": _pct(lat, 99) * 1e6,
        "hit_rate": (c["hits"] + c["late_hits"]) / n if app else nan,
        "late_hit_rate": c["late_hits"] / n if app else nan,
        "demand_misses": c["misses"] if app else nan,
        "prefetch_issued": issued,
        "accuracy": (c["prefetch_useful"] / issued) if issued else nan,
        "wasted_mib": c["wasted_bytes"] / 2**20,
        "app_read_mib": (c["demand_bytes"] + c["prefetch_bytes"]) / 2**20 if app else trace.requested_bytes / 2**20,
        "device_read_mib": (io1 - io0) / 2**20,
        "peak_cache_mib": (cache.peak_bytes if cache is not None else ledger.peak_bytes) / 2**20,
        "total_ms": wall * 1e3,
        "io_wait_ms": sum(lat) * 1e3,
        "throughput_MBps": trace.requested_bytes / wall / 1e6,
        "predictor_cpu_ms": c["predictor_cpu_s"] * 1e3,
        "cpu_s": cpu_s,
        "cpu_util": cpu_s / wall,
        "peak_rss_extra_mib": (peak_rss_kb - rss0) / 1024 if rss_reset else nan,
    }

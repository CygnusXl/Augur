"""Trace-driven simulator with a single FIFO storage device.

What it models: a workload that computes for ``think_time_s`` between requests,
a bounded cache, and one storage device that serves reads in order. Prefetch
reads queue ahead of later demand reads, so over-eager prefetching delays real
requests (bandwidth contention). A request for an item whose prefetch is still
in flight waits only for the remainder (a late hit).

What it does not model: the OS page cache, parallel queues, or real device
behaviour. Device parameters are nominal assumptions, not measurements of any
specific drive. Use the real-I/O harness to confirm rankings.
"""

from __future__ import annotations

import math
import time
from collections import deque
from dataclasses import dataclass, field
from statistics import median
from typing import Dict, List, Optional

from ..core.cache import ByteCache, Entry
from ..core.predictors import NoPredictor, Predictor
from ..core.scheduler import PrefetchScheduler, SchedulerConfig
from .traces import Trace

HIT_COST_S = 2e-6  # serving from memory


@dataclass(frozen=True)
class DeviceModel:
    name: str
    latency_s: float  # per non-adjacent read
    bandwidth_Bps: float

    def service_time(self, size: int, adjacent: bool) -> float:
        return (0.0 if adjacent else self.latency_s) + size / self.bandwidth_Bps


# Nominal, order-of-magnitude assumptions. Not measured.
DEVICES = {
    "hdd": DeviceModel("hdd", 8e-3, 150e6),
    "sata_ssd": DeviceModel("sata_ssd", 1e-4, 500e6),
    "nvme": DeviceModel("nvme", 8e-5, 3e9),
}


@dataclass
class SimConfig:
    cache_bytes: int
    policy: str = "lru"
    device: DeviceModel = field(default_factory=lambda: DEVICES["sata_ssd"])
    think_time_s: float = 1e-4
    charge_overhead: bool = False  # add measured predictor CPU time to the simulated clock


@dataclass
class RunResult:
    trace_name: str
    latencies: List[float]
    total_time_s: float
    requested_bytes: int
    counters: Dict[str, float]

    def summary(self) -> Dict[str, float]:
        n = len(self.latencies)
        lat = sorted(self.latencies)

        def pct(p: float) -> float:
            return lat[min(n - 1, max(0, math.ceil(p / 100.0 * n) - 1))]

        c = self.counters
        issued = c["prefetch_issued"]
        return {
            "n": n,
            "mean_us": sum(lat) / n * 1e6,
            "median_us": median(lat) * 1e6,
            "p95_us": pct(95) * 1e6,
            "p99_us": pct(99) * 1e6,
            "hit_rate": (c["hits"] + c["late_hits"]) / n,
            "late_hit_rate": c["late_hits"] / n,
            "demand_misses": c["misses"],
            "prefetch_issued": issued,
            "accuracy": (c["prefetch_useful"] / issued) if issued else float("nan"),
            "wasted_mib": c["wasted_bytes"] / 2**20,
            "read_mib": (c["demand_bytes"] + c["prefetch_bytes"]) / 2**20,
            "peak_cache_mib": c["peak_cache_bytes"] / 2**20,
            "peak_inflight_mib": c["peak_inflight_bytes"] / 2**20,
            "total_ms": self.total_time_s * 1e3,
            "throughput_MBps": self.requested_bytes / self.total_time_s / 1e6,
            "predictor_cpu_ms": c["predictor_cpu_s"] * 1e3,
        }


def simulate(
    trace: Trace,
    cfg: SimConfig,
    predictor: Optional[Predictor] = None,
    scheduler: Optional[PrefetchScheduler] = None,
) -> RunResult:
    predictor = predictor or NoPredictor()
    scheduler = scheduler or PrefetchScheduler(SchedulerConfig())
    sizes = trace.sizes
    dev = cfg.device
    depth = scheduler.cfg.depth

    c: Dict[str, float] = dict(
        hits=0, late_hits=0, misses=0, demand_bytes=0, prefetch_issued=0, prefetch_bytes=0,
        prefetch_useful=0, wasted_bytes=0, predictor_cpu_s=0.0, peak_cache_bytes=0,
        peak_inflight_bytes=0,
    )

    def on_evict(_key, entry: Entry) -> None:
        if entry.prefetched and not entry.used:
            c["wasted_bytes"] += entry.size
            scheduler.record_outcome(False)

    cache = ByteCache(cfg.cache_bytes, cfg.policy, on_evict=on_evict)
    inflight: Dict[int, float] = {}  # item -> completion time
    queue: deque = deque()  # (completion, item, size) in issue order
    inflight_bytes = 0
    device_free = 0.0
    last_read: Optional[int] = None

    def issue_read(at: float, item: int) -> float:
        nonlocal device_free, last_read
        start = max(at, device_free)
        adjacent = last_read is not None and item == last_read + 1
        done = start + dev.service_time(sizes[item], adjacent)
        device_free = done
        last_read = item
        return done

    def finalize(t: float) -> None:
        nonlocal inflight_bytes
        while queue and queue[0][0] <= t:
            comp, item, size = queue.popleft()
            if inflight.get(item) != comp:
                continue  # consumed early by a late hit
            del inflight[item]
            inflight_bytes -= size
            if not cache.put(item, size, prefetched=True):
                c["wasted_bytes"] += size
                scheduler.record_outcome(False)

    now = 0.0
    latencies: List[float] = []
    for item in trace.accesses:
        now += cfg.think_time_s
        t = now
        finalize(t)
        size = sizes[item]
        entry = cache.peek(item)
        if entry is not None:
            first_use = entry.prefetched and not entry.used
            cache.get(item)
            c["hits"] += 1
            if first_use:
                c["prefetch_useful"] += 1
                scheduler.record_outcome(True)
            latency = HIT_COST_S
        elif item in inflight:
            comp = inflight.pop(item)
            inflight_bytes -= size
            latency = max(0.0, comp - t) + HIT_COST_S
            cache.put(item, size, prefetched=True)
            cache.get(item)
            c["late_hits"] += 1
            c["prefetch_useful"] += 1
            scheduler.record_outcome(True)
        else:
            done = issue_read(t, item)
            latency = done - t
            c["misses"] += 1
            c["demand_bytes"] += size
            cache.put(item, size, prefetched=False)
        latencies.append(latency)
        now = t + latency

        t0 = time.perf_counter()
        predictor.observe(item)
        cands = predictor.predict(depth)
        dt = time.perf_counter() - t0
        c["predictor_cpu_s"] += dt
        if cfg.charge_overhead:
            now += dt

        finalize(now)
        chosen = scheduler.select(
            cands, lambda i: i in cache, lambda i: i in inflight, sizes, len(inflight), inflight_bytes
        )
        for it in chosen:
            done = issue_read(now, it)
            inflight[it] = done
            queue.append((done, it, sizes[it]))
            inflight_bytes += sizes[it]
            c["prefetch_issued"] += 1
            c["prefetch_bytes"] += sizes[it]
        if inflight_bytes > c["peak_inflight_bytes"]:
            c["peak_inflight_bytes"] = inflight_bytes

    # Anything prefetched but never used counts as waste, including reads still in flight.
    for _key, e in cache.entries():
        if e.prefetched and not e.used:
            c["wasted_bytes"] += e.size
    for comp, it, size in queue:
        if inflight.get(it) == comp:
            c["wasted_bytes"] += size
    c["peak_cache_bytes"] = cache.peak_bytes
    return RunResult(trace.name, latencies, now, trace.requested_bytes, c)

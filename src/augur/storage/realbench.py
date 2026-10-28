"""Real-I/O benchmark: workloads x configurations x repeats, on a real drive.

    python -m augur.storage.realbench --dir /folder/on/the/drive --label mypc

Each workload gets its own data file in --dir (deleted afterwards unless
--keep). Every run starts with the file evicted from the page cache.
Configuration order is shuffled within each repeat so slow drift (thermal
state, background activity) is not charged to one configuration.

Configurations
    os-default       no application cache; kernel readahead on (the "OS cache only" baseline)
    os-noreadahead   same, with readahead off (POSIX_FADV_RANDOM)
    lru              application LRU cache, no prefetch
    sequential       LRU + sequential prefetch
    stride           LRU + stride prefetch
    markov1/markov2  LRU + learned-from-history prefetch
    markov2+gate     markov2 that backs off when prefetches are wasted
    oracle           clairvoyant upper bound (knows the future from the trace)

The access orders are still synthetic (see traces.py); the reads, the cache
state, the CPU and memory costs are real. Results are specific to your
hardware and are not comparable across machines.
"""

from __future__ import annotations

import argparse
import csv
import os
import platform
import random
import shutil
import tempfile
import time
from dataclasses import dataclass
from statistics import median
from typing import Callable, Dict, List

from ..core.predictors import NoPredictor, Predictor
from ..core.scheduler import PrefetchScheduler, SchedulerConfig
from .bench import CONFIGS as SIM_CONFIGS
from .realio import (
    DataFile,
    RealConfig,
    calibrate,
    fs_type,
    mem_total_mib,
    rotational,
    run_real,
)
from .traces import MiB, WORKLOADS, Trace

BASELINES = ("os-default", "lru")


@dataclass(frozen=True)
class RealSpec:
    name: str
    make_predictor: Callable[[Trace], Predictor]
    mode: str = "app"
    policy: str = "lru"
    adaptive: bool = False
    readahead: bool = True


def _specs() -> Dict[str, RealSpec]:
    specs = {
        "os-default": RealSpec("os-default", lambda t: NoPredictor(), mode="os"),
        "os-noreadahead": RealSpec("os-noreadahead", lambda t: NoPredictor(), mode="os", readahead=False),
    }
    for name, s in SIM_CONFIGS.items():
        specs[name] = RealSpec(name, s.make_predictor, "app", s.policy, s.adaptive)
    return specs


REAL_CONFIGS = _specs()
DEFAULT_CONFIGS = ["os-default", "os-noreadahead", "lru", "sequential", "markov2", "oracle"]
DEFAULT_WORKLOADS = ["recurring_routines", "dl_fixed_order", "dl_reshuffled", "sequential", "random"]
NUMERIC = [
    "mean_us", "median_us", "p95_us", "p99_us", "hit_rate", "late_hit_rate", "demand_misses",
    "prefetch_issued", "accuracy", "wasted_mib", "app_read_mib", "device_read_mib", "peak_cache_mib",
    "total_ms", "io_wait_ms", "throughput_MBps", "predictor_cpu_ms", "cpu_s", "cpu_util", "peak_rss_extra_mib",
]


def _med(values: List[float]) -> float:
    vals = [v for v in values if v == v]
    return median(vals) if vals else float("nan")


def machine_info(directory: str) -> Dict[str, object]:
    rot = rotational(directory)
    ram = mem_total_mib()
    return {
        "platform": platform.platform(),
        "cpu": platform.processor() or platform.machine(),
        "cpus": os.cpu_count(),
        "ram_gib": round(ram / 1024, 1) if ram else None,
        "python": platform.python_version(),
        "filesystem": fs_type(directory),
        "drive": {True: "rotational (HDD)", False: "non-rotational (flash)", None: "unknown"}[rot],
    }


def collect(args: argparse.Namespace) -> tuple[List[Dict], List[Dict]]:
    rows: List[Dict] = []
    cals: List[Dict] = []
    for wname in args.workloads:
        trace = WORKLOADS[wname](args.accesses, args.seed)
        path = os.path.join(args.dir, f"augur_{wname}_{os.getpid()}.bin")
        need = sum(trace.sizes.values())
        free = shutil.disk_usage(args.dir).free
        if free < need * 1.2 + 64 * MiB:
            raise SystemExit(f"not enough free space in {args.dir} for {wname}: need {need / MiB:.0f} MiB")
        print(f"\n[{wname}] writing {need / MiB:.0f} MiB ...", flush=True)
        df = DataFile(path, trace.sizes)
        try:
            df.create(args.seed)
            df.open()
            cal = calibrate(df, seed=args.seed)
            cal["workload"] = wname
            cals.append(cal)
            note = "" if cal["ratio"] >= 1.5 else "  WARNING: cold reads are not clearly slower; results unreliable"
            print(f"[{wname}] cold/warm random read ratio {cal['ratio']:.1f}x "
                  f"(cold {cal['cold_us']:.0f} us, warm {cal['warm_us']:.0f} us){note}", flush=True)
            cache_bytes = max(1 * MiB, int(args.cache_fraction * trace.unique_bytes))
            rng = random.Random(args.seed + 1)
            for rep in range(args.repeats):
                order = list(args.configs)
                rng.shuffle(order)
                for cn in order:
                    spec = REAL_CONFIGS[cn]
                    cfg = RealConfig(
                        cache_bytes=cache_bytes, policy=spec.policy, think_s=args.think_us * 1e-6,
                        workers=args.workers, readahead=spec.readahead, mode=spec.mode,
                    )
                    sched = PrefetchScheduler(
                        SchedulerConfig(threshold=args.threshold, depth=args.depth, adaptive=spec.adaptive)
                    )
                    s = run_real(trace, df, cfg, spec.make_predictor(trace), sched)
                    rows.append({"workload": wname, "config": cn, "repeat": rep, **s})
                    print(f"  rep {rep} {cn:15s} {s['total_ms'] / 1e3:8.2f} s   p99 {s['p99_us']:9.0f} us   "
                          f"device read {s['device_read_mib']:8.1f} MiB", flush=True)
        finally:
            df.remove()
    return rows, cals


def aggregate(rows: List[Dict], args: argparse.Namespace) -> List[Dict]:
    out = []
    for wname in args.workloads:
        for cn in args.configs:
            sel = [r for r in rows if r["workload"] == wname and r["config"] == cn]
            if not sel:
                continue
            agg = {"workload": wname, "config": cn, "repeats": len(sel)}
            for f in NUMERIC:
                agg[f] = _med([r[f] for r in sel])
            tot = [r["total_ms"] for r in sel]
            agg["total_ms_min"], agg["total_ms_max"] = min(tot), max(tot)
            out.append(agg)
    for wname in args.workloads:
        grp = {a["config"]: a for a in out if a["workload"] == wname}
        for a in grp.values():
            for base in BASELINES:
                b = grp.get(base)
                a[f"speedup_vs_{base}"] = b["total_ms"] / a["total_ms"] if b else float("nan")
            lru = grp.get("lru")
            if lru and a["config"] not in ("os-default", "os-noreadahead") and lru["demand_misses"]:
                a["coverage"] = (lru["demand_misses"] - a["demand_misses"]) / lru["demand_misses"]
            else:
                a["coverage"] = float("nan")
    return out


def fmt(v: float, digits: int = 1, pct: bool = False) -> str:
    if v != v:
        return "-"
    return f"{v * 100:.0f}%" if pct else f"{v:.{digits}f}"


def markdown(agg: List[Dict], cals: List[Dict], info: Dict, args: argparse.Namespace) -> str:
    lines = [
        f"# Real-I/O results: {args.label}",
        "",
        f"Machine: {info['platform']}, {info['cpus']} CPUs, {info['ram_gib']} GiB RAM, Python {info['python']}. "
        f"Files on `{info['filesystem']}`, drive reported as **{info['drive']}**.",
        "",
        f"{args.repeats} repeats per cell (median shown; time column also shows min-max), "
        f"{args.accesses} accesses per workload, application cache = {args.cache_fraction:.0%} of unique bytes, "
        f"think time {args.think_us:g} us, prefetch depth {args.depth}, threshold {args.threshold}, "
        f"{args.workers} prefetch threads. Every run started with the file evicted from the page cache.",
        "",
        "Cold/warm calibration (random reads on each data file; a ratio below 1.5 means results are unreliable): "
        + ", ".join(f"{c['workload']} {c['ratio']:.0f}x" for c in cals) + ".",
        "",
        "Access orders are synthetic; reads, caches, CPU and memory are real. `speedup` is end-to-end time versus "
        "the named baseline (above 1.0 is faster). `device MiB` is what the kernel actually read from the "
        "device (readahead included). `cpu` is process CPU time over wall time. `RSS+` is extra peak resident memory.",
        "",
    ]
    for wname in args.workloads:
        lines += [
            f"## {wname}",
            "",
            "| config | mean us | p95 us | p99 us | hit | accuracy | wasted MiB | device MiB | cpu | RSS+ MiB | "
            "predictor ms | time s (min-max) | vs os-default | vs lru |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
        for r in [a for a in agg if a["workload"] == wname]:
            lines.append(
                f"| {r['config']} | {fmt(r['mean_us'], 0)} | {fmt(r['p95_us'], 0)} | {fmt(r['p99_us'], 0)} "
                f"| {fmt(r['hit_rate'], pct=True)} | {fmt(r['accuracy'], pct=True)} | {fmt(r['wasted_mib'])} "
                f"| {fmt(r['device_read_mib'])} | {fmt(r['cpu_util'], pct=True)} | {fmt(r['peak_rss_extra_mib'])} "
                f"| {fmt(r['predictor_cpu_ms'])} "
                f"| {r['total_ms'] / 1e3:.2f} ({r['total_ms_min'] / 1e3:.2f}-{r['total_ms_max'] / 1e3:.2f}) "
                f"| {fmt(r['speedup_vs_os-default'], 2)}x | {fmt(r['speedup_vs_lru'], 2)}x |"
            )
        lines.append("")
    return "\n".join(lines)


def main(argv: List[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dir", default=None, help="folder on the drive to test (required unless --allow-tmp)")
    p.add_argument("--label", default="run")
    p.add_argument("--out", default="results/real")
    p.add_argument("--accesses", type=int, default=6000)
    p.add_argument("--repeats", type=int, default=3)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--cache-fraction", type=float, default=0.05)
    p.add_argument("--think-us", type=float, default=1000.0)
    p.add_argument("--depth", type=int, default=4)
    p.add_argument("--threshold", type=float, default=0.4)
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--workloads", nargs="+", default=DEFAULT_WORKLOADS, choices=list(WORKLOADS))
    p.add_argument("--configs", nargs="+", default=DEFAULT_CONFIGS, choices=list(REAL_CONFIGS))
    p.add_argument("--allow-tmp", action="store_true", help="use the system temp dir (may be RAM-backed)")
    args = p.parse_args(argv)

    if not hasattr(os, "posix_fadvise"):
        raise SystemExit("Linux only: posix_fadvise is not available.")
    if args.dir is None:
        if not args.allow_tmp:
            raise SystemExit("Pass --dir with a folder on the drive you want to test.")
        args.dir = tempfile.gettempdir()
    if not os.path.isdir(args.dir):
        raise SystemExit(f"--dir {args.dir!r} does not exist (use a real folder, not a placeholder).")
    if fs_type(args.dir) in ("tmpfs", "ramfs"):
        raise SystemExit(f"{args.dir} is on RAM-backed {fs_type(args.dir)}; pick a folder on a real drive.")
    for base in BASELINES:
        if base not in args.configs:
            print(f"note: '{base}' not selected, speedups against it will be blank.")

    info = machine_info(args.dir)
    print("Machine:", info)
    t0 = time.time()
    rows, cals = collect(args)
    agg = aggregate(rows, args)
    out = os.path.join(args.out, args.label)
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "runs.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    md = markdown(agg, cals, info, args)
    with open(os.path.join(out, "summary.md"), "w") as fh:
        fh.write(md + "\n")
    print(md)
    print(f"\nDone in {(time.time() - t0) / 60:.1f} min. Results in {out}/ (runs.csv, summary.md)")


if __name__ == "__main__":
    main()

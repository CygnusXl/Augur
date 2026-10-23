"""Benchmark runner: workloads x configurations x seeds, on identical traces.

    python -m augur.bench --device sata_ssd --seeds 3 --out results

Every configuration sees the same trace, the same cache byte budget, the same
device model and the same prefetch limits. Numbers are medians across seeds.
"""

from __future__ import annotations

import argparse
import csv
import math
import os
from dataclasses import dataclass
from statistics import median
from typing import Callable, Dict, List

from .predictors import (
    MarkovPredictor,
    NoPredictor,
    OraclePredictor,
    Predictor,
    SequentialPredictor,
    StridePredictor,
)
from .scheduler import PrefetchScheduler, SchedulerConfig
from .simulator import DEVICES, SimConfig, simulate
from .traces import MiB, WORKLOADS, Trace


@dataclass(frozen=True)
class ConfigSpec:
    name: str
    make_predictor: Callable[[Trace], Predictor]
    policy: str = "lru"
    adaptive: bool = False
    note: str = ""


CONFIGS: Dict[str, ConfigSpec] = {
    c.name: c
    for c in [
        ConfigSpec("lru", lambda t: NoPredictor(), "lru", note="LRU cache, no prefetch"),
        ConfigSpec("lfu", lambda t: NoPredictor(), "lfu", note="LFU cache, no prefetch"),
        ConfigSpec("sequential", lambda t: SequentialPredictor(), note="conventional readahead"),
        ConfigSpec("stride", lambda t: StridePredictor(), note="stride heuristic"),
        ConfigSpec("markov1", lambda t: MarkovPredictor(1), note="order-1 transition model"),
        ConfigSpec("markov2", lambda t: MarkovPredictor(2), note="order-2 with back-off"),
        ConfigSpec("markov2+gate", lambda t: MarkovPredictor(2), adaptive=True, note="order-2, backs off when wasteful"),
        ConfigSpec("markov2-naive", lambda t: MarkovPredictor(2, min_support=1, smoothing=0.0, name="markov2-naive"),
                   note="order-2 trusting single observations (ablation)"),
        ConfigSpec("oracle", lambda t: OraclePredictor(t.accesses), note="clairvoyant upper bound"),
    ]
}
BASELINE = "lru"


def run_one(trace: Trace, spec: ConfigSpec, args: argparse.Namespace) -> Dict[str, float]:
    cache_bytes = max(1 * MiB, int(args.cache_fraction * trace.unique_bytes))
    cfg = SimConfig(
        cache_bytes=cache_bytes,
        policy=spec.policy,
        device=DEVICES[args.device],
        think_time_s=args.think_us * 1e-6,
        charge_overhead=args.charge_overhead,
    )
    sched = PrefetchScheduler(
        SchedulerConfig(threshold=args.threshold, depth=args.depth, adaptive=spec.adaptive)
    )
    return simulate(trace, cfg, spec.make_predictor(trace), sched).summary()


def _med(values: List[float]) -> float:
    vals = [v for v in values if v == v]  # drop NaN
    return median(vals) if vals else float("nan")


def collect(args: argparse.Namespace) -> List[Dict]:
    rows: List[Dict] = []
    for wname in args.workloads:
        for seed in range(args.seeds):
            trace = WORKLOADS[wname](args.accesses, seed)
            results = {cn: run_one(trace, CONFIGS[cn], args) for cn in args.configs}
            base = results.get(BASELINE)
            for cn, s in results.items():
                row = {"workload": wname, "config": cn, "seed": seed, **s}
                if base is not None:
                    bm = base["demand_misses"]
                    row["coverage"] = (bm - s["demand_misses"]) / bm if bm else float("nan")
                    row["speedup_vs_lru"] = base["total_ms"] / s["total_ms"]
                rows.append(row)
    return rows


def aggregate(rows: List[Dict]) -> List[Dict]:
    keys = {(r["workload"], r["config"]) for r in rows}
    out = []
    fields = [k for k in rows[0] if k not in ("workload", "config", "seed")]
    for wname, cn in sorted(keys, key=lambda k: (list(WORKLOADS).index(k[0]), list(CONFIGS).index(k[1]))):
        sel = [r for r in rows if r["workload"] == wname and r["config"] == cn]
        agg = {"workload": wname, "config": cn}
        for f in fields:
            agg[f] = _med([r[f] for r in sel if f in r])
        out.append(agg)
    return out


def fmt(v: float, digits: int = 1, pct: bool = False) -> str:
    if v != v:
        return "-"
    return f"{v * 100:.0f}%" if pct else f"{v:.{digits}f}"


def markdown(agg: List[Dict], args: argparse.Namespace) -> str:
    lines = [
        f"# Simulated results: {args.device}",
        "",
        f"Device `{args.device}` is a nominal model, not a measurement. {args.seeds} seeds, "
        f"{args.accesses} accesses per trace, cache = {args.cache_fraction:.0%} of unique bytes, "
        f"think time {args.think_us:g} us, prefetch depth {args.depth}, threshold {args.threshold}. "
        "Values are medians across seeds. `speedup` is end-to-end time versus the LRU baseline "
        "(above 1.0 is faster). `coverage` is the share of LRU's demand misses avoided.",
        "",
    ]
    for wname in args.workloads:
        lines += [
            f"## {wname}",
            "",
            "| config | mean us | p99 us | hit | accuracy | coverage | wasted MiB | read MiB | time ms | speedup |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
        for r in [a for a in agg if a["workload"] == wname]:
            lines.append(
                f"| {r['config']} | {fmt(r['mean_us'])} | {fmt(r['p99_us'])} | {fmt(r['hit_rate'], pct=True)} "
                f"| {fmt(r['accuracy'], pct=True)} | {fmt(r.get('coverage', float('nan')), pct=True)} "
                f"| {fmt(r['wasted_mib'])} | {fmt(r['read_mib'])} | {fmt(r['total_ms'])} "
                f"| {fmt(r.get('speedup_vs_lru', float('nan')), 2)}x |"
            )
        lines.append("")
    return "\n".join(lines)


def main(argv: List[str] | None = None) -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--device", choices=list(DEVICES), default="sata_ssd")
    p.add_argument("--seeds", type=int, default=3)
    p.add_argument("--accesses", type=int, default=20000)
    p.add_argument("--cache-fraction", type=float, default=0.05)
    p.add_argument("--think-us", type=float, default=100.0)
    p.add_argument("--depth", type=int, default=4)
    p.add_argument("--threshold", type=float, default=0.4)
    p.add_argument("--workloads", nargs="+", default=list(WORKLOADS), choices=list(WORKLOADS))
    p.add_argument("--configs", nargs="+", default=list(CONFIGS), choices=list(CONFIGS))
    p.add_argument("--charge-overhead", action="store_true",
                   help="add measured predictor CPU time to the simulated clock (not deterministic)")
    p.add_argument("--out", default="results")
    args = p.parse_args(argv)

    rows = collect(args)
    agg = aggregate(rows)
    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, f"runs_{args.device}.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    md = markdown(agg, args)
    with open(os.path.join(args.out, f"summary_{args.device}.md"), "w") as fh:
        fh.write(md + "\n")
    print(md)


if __name__ == "__main__":
    main()

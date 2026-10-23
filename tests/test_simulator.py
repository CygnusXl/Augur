import random

import pytest

from augur.predictors import Candidate, MarkovPredictor, NoPredictor, OraclePredictor, Predictor, SequentialPredictor
from augur.scheduler import PrefetchScheduler, SchedulerConfig
from augur.simulator import DEVICES, SimConfig, simulate
from augur.traces import MiB, WORKLOADS, sequential


def cfg(trace, frac=0.05, **kw):
    return SimConfig(cache_bytes=max(MiB, int(frac * trace.unique_bytes)), **kw)


def run(trace, predictor, **kw):
    sched_cfg = kw.pop("sched", SchedulerConfig())
    return simulate(trace, cfg(trace, **kw), predictor, PrefetchScheduler(sched_cfg))


@pytest.mark.parametrize("name", list(WORKLOADS))
def test_deterministic(name):
    t = WORKLOADS[name](1500, 3)
    a = run(t, MarkovPredictor(2)).summary()
    b = run(t, MarkovPredictor(2)).summary()
    a.pop("predictor_cpu_ms"), b.pop("predictor_cpu_ms")
    assert repr(a) == repr(b)  # repr so NaN accuracy compares equal


@pytest.mark.parametrize("name", list(WORKLOADS))
def test_every_request_is_accounted_for(name):
    t = WORKLOADS[name](1500, 1)
    r = run(t, MarkovPredictor(1))
    c = r.counters
    assert c["hits"] + c["late_hits"] + c["misses"] == len(t.accesses) == len(r.latencies)
    assert all(x > 0 for x in r.latencies)


@pytest.mark.parametrize("name", list(WORKLOADS))
def test_memory_limits_respected(name):
    t = WORKLOADS[name](2000, 2)
    sched = SchedulerConfig(byte_budget=2 * MiB, max_inflight=4)
    r = run(t, OraclePredictor(t.accesses), sched=sched)
    assert r.counters["peak_cache_bytes"] <= max(MiB, int(0.05 * t.unique_bytes))
    assert r.counters["peak_inflight_bytes"] <= 2 * MiB


class Garbage(Predictor):
    """Adversarial: nonsense ids, absurd confidences, repeats, negatives."""

    def __init__(self, seed=0):
        self.rng = random.Random(seed)

    def predict(self, depth):
        return [Candidate(self.rng.randint(-50, 10**9), self.rng.choice([0.0, 1.0, 5.0, -1.0]))
                for _ in range(depth * 3)]


class Wrong(Predictor):
    """Always confidently predicts valid but never-requested items."""

    def __init__(self, ids):
        self.ids = ids
        self.i = 0

    def predict(self, depth):
        self.i += 1
        return [Candidate(self.ids[(self.i + j) % len(self.ids)], 1.0) for j in range(depth)]


def test_garbage_predictions_cannot_crash_or_change_what_is_served():
    t = WORKLOADS["random"](1500, 0)
    base = run(t, NoPredictor())
    bad = run(t, Garbage(1))
    assert len(bad.latencies) == len(base.latencies) == len(t.accesses)
    assert bad.counters["hits"] + bad.counters["late_hits"] + bad.counters["misses"] == len(t.accesses)
    bad_cache_bytes = max(MiB, int(0.05 * t.unique_bytes))
    assert bad.counters["peak_cache_bytes"] <= bad_cache_bytes


def test_always_wrong_prefetching_is_counted_as_waste_not_hits():
    t = WORKLOADS["sequential"](1000, 0)
    unused = [i for i in t.sizes if i not in set(t.accesses)] or list(t.sizes)[-50:]
    r = run(t, Wrong(unused[:50]))
    s = r.summary()
    assert r.counters["prefetch_useful"] == 0 or s["accuracy"] < 0.2
    assert s["wasted_mib"] > 0
    assert s["read_mib"] > s["wasted_mib"]


def test_no_predictor_issues_no_prefetch():
    r = run(WORKLOADS["zipf_workingset"](1000, 0), NoPredictor())
    assert r.counters["prefetch_issued"] == 0 and r.counters["wasted_bytes"] == 0


def test_oracle_beats_lru_on_sequential_and_sequential_readahead_matches():
    t = sequential(3000, 0)
    lru = run(t, NoPredictor())
    seq = run(t, SequentialPredictor())
    orc = run(t, OraclePredictor(t.accesses))
    assert orc.total_time_s < lru.total_time_s
    assert seq.total_time_s < lru.total_time_s
    assert orc.summary()["accuracy"] > 0.95


def test_slower_device_means_longer_runtime():
    t = WORKLOADS["random"](800, 0)
    fast = run(t, NoPredictor(), device=DEVICES["nvme"])
    slow = run(t, NoPredictor(), device=DEVICES["hdd"])
    assert slow.total_time_s > fast.total_time_s


def test_read_volume_equals_demand_plus_prefetch():
    t = WORKLOADS["dl_fixed_order"](2000, 0)
    r = run(t, MarkovPredictor(1))
    c = r.counters
    assert c["demand_bytes"] + c["prefetch_bytes"] > 0
    assert r.summary()["read_mib"] == pytest.approx((c["demand_bytes"] + c["prefetch_bytes"]) / 2**20)


def test_cache_larger_than_working_set_never_evicts_wastefully():
    t = WORKLOADS["zipf_workingset"](2000, 0)
    r = simulate(t, SimConfig(cache_bytes=10 * t.unique_bytes), NoPredictor(), PrefetchScheduler())
    assert r.counters["misses"] == t.unique_items

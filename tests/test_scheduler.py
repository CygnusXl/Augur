from augur.predictors import Candidate
from augur.scheduler import PrefetchScheduler, SchedulerConfig

SIZES = {i: 1000 for i in range(50)}
NEVER = lambda i: False


def select(sched, cands, cached=NEVER, inflight=NEVER, n=0, b=0, sizes=SIZES):
    return sched.select([Candidate(i, c) for i, c in cands], cached, inflight, sizes, n, b)


def test_threshold_filters_low_confidence():
    s = PrefetchScheduler(SchedulerConfig(threshold=0.5))
    assert select(s, [(1, 0.9), (2, 0.49), (3, 0.5)]) == [1, 3]


def test_depth_caps_new_reads():
    s = PrefetchScheduler(SchedulerConfig(depth=2))
    assert select(s, [(i, 1.0) for i in range(10)]) == [0, 1]


def test_inflight_count_cap():
    s = PrefetchScheduler(SchedulerConfig(max_inflight=3, depth=8))
    assert select(s, [(i, 1.0) for i in range(10)], n=1) == [0, 1]


def test_byte_budget_cap():
    s = PrefetchScheduler(SchedulerConfig(byte_budget=2500, depth=8))
    assert select(s, [(i, 1.0) for i in range(10)], b=500) == [0, 1]


def test_skips_cached_inflight_unknown_and_duplicates():
    s = PrefetchScheduler()
    out = select(s, [(1, 1), (2, 1), (3, 1), (999, 1), (3, 1), (4, 1)],
                 cached=lambda i: i == 1, inflight=lambda i: i == 2)
    assert out == [3, 4]


def test_adaptive_backs_off_and_probes():
    cfg = SchedulerConfig(adaptive=True, window=20, min_samples=10, accuracy_floor=0.3, probe_every=5, depth=4)
    s = PrefetchScheduler(cfg)
    assert not s.backed_off
    for _ in range(20):
        s.record_outcome(False)
    assert s.backed_off and s.rolling_accuracy == 0.0
    cands = [(i, 1.0) for i in range(10)]
    results = [select(s, cands) for _ in range(10)]
    # Silent most of the time; a single-item probe every probe_every calls.
    assert [len(r) for r in results].count(0) == 8
    assert [len(r) for r in results].count(1) == 2


def test_adaptive_recovers_when_accuracy_returns():
    s = PrefetchScheduler(SchedulerConfig(adaptive=True, window=20, min_samples=10, accuracy_floor=0.3))
    for _ in range(20):
        s.record_outcome(False)
    for _ in range(20):
        s.record_outcome(True)
    assert not s.backed_off


def test_non_adaptive_never_backs_off():
    s = PrefetchScheduler(SchedulerConfig(adaptive=False))
    for _ in range(100):
        s.record_outcome(False)
    assert not s.backed_off

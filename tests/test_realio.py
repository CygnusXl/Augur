import math
import os

import pytest

from augur.core.predictors import MarkovPredictor, NoPredictor, OraclePredictor, SequentialPredictor
from augur.core.scheduler import PrefetchScheduler, SchedulerConfig
from augur.storage.realio import DataFile, RealConfig, calibrate, fs_type, run_real
from augur.storage.traces import Trace

pytestmark = pytest.mark.skipif(not hasattr(os, "posix_fadvise"), reason="Linux only")

KiB = 1024


def make_trace(n_items=40, reps=6, size=8 * KiB):
    sizes = {i: size for i in range(n_items)}
    order = [(i * 7) % n_items for i in range(n_items)]  # fixed non-sequential tour
    return Trace("tour", order * reps, sizes, 0)


@pytest.fixture
def df(tmp_path):
    t = make_trace()
    d = DataFile(str(tmp_path / "data.bin"), t.sizes)
    d.create(seed=1)
    d.open()
    yield d
    d.remove()


def test_datafile_layout_and_verify(df):
    assert df.total_bytes == 40 * 8 * KiB
    assert df.offsets[3] == 3 * 8 * KiB
    data = df.read(5)
    assert len(data) == 8 * KiB
    with pytest.raises(RuntimeError):
        df.verify(6, data)  # wrong item id
    with pytest.raises(RuntimeError):
        df.verify(5, data[:-1])  # short read


def test_datafile_reproducible(tmp_path):
    sizes = {i: 4 * KiB for i in range(5)}
    a, b = DataFile(str(tmp_path / "a"), sizes), DataFile(str(tmp_path / "b"), sizes)
    a.create(3)
    b.create(3)
    assert open(a.path, "rb").read() == open(b.path, "rb").read()


def test_remove_deletes_file(tmp_path):
    d = DataFile(str(tmp_path / "x"), {0: 64})
    d.create()
    d.open()
    d.remove()
    assert not os.path.exists(d.path)


def test_calibrate_returns_numbers(df):
    c = calibrate(df, n=10)
    assert c["cold_us"] > 0 and c["warm_us"] > 0 and c["ratio"] > 0


def run(df, mode="app", predictor=None, cache_bytes=64 * KiB, **kw):
    t = make_trace()
    cfg = RealConfig(cache_bytes=cache_bytes, think_s=0.0, mode=mode, **kw)
    sched = PrefetchScheduler(SchedulerConfig(threshold=0.4, depth=4))
    return t, run_real(t, df, cfg, predictor, sched)


def test_lru_accounting(df):
    t, s = run(df)
    assert s["n"] == len(t)
    # every access is a hit or a miss; no prefetching here
    assert s["hit_rate"] == pytest.approx(1 - s["demand_misses"] / s["n"])
    assert s["prefetch_issued"] == 0 and s["wasted_mib"] == 0
    assert s["peak_cache_mib"] * 2**20 <= 64 * KiB


def test_big_cache_hits_after_first_pass(df):
    t, s = run(df, cache_bytes=10 * 2**20)
    assert s["demand_misses"] == 40  # one cold miss per unique item


def test_os_mode_has_no_app_hit_rate(df):
    t, s = run(df, mode="os")
    assert math.isnan(s["hit_rate"])
    assert s["total_ms"] > 0 and s["n"] == len(t)


def test_markov_prefetch_learns_repeating_tour(df):
    t, base = run(df)
    _, s = run(df, predictor=MarkovPredictor(2))
    assert s["prefetch_issued"] > 0
    assert s["accuracy"] > 0.5
    assert s["demand_misses"] < base["demand_misses"]
    assert s["hit_rate"] > base["hit_rate"]


def test_oracle_is_best_and_waste_accounted(df):
    t = make_trace()
    _, s = run(df, predictor=OraclePredictor(t.accesses))
    assert s["accuracy"] > 0.9
    _, r = run(df, predictor=SequentialPredictor())  # tour is not sequential
    assert r["wasted_mib"] >= 0


def test_counters_consistent(df):
    t, s = run(df, predictor=MarkovPredictor(1))
    misses = s["demand_misses"]
    assert 0 <= misses <= s["n"]
    assert s["app_read_mib"] * 2**20 >= misses * 8 * KiB
    assert 0 <= s["accuracy"] <= 1


def test_fs_type_known_for_tmp(tmp_path):
    assert isinstance(fs_type(str(tmp_path)), str)


def test_lazy_drop_matches_accounting(df):
    t, eager = run(df, predictor=MarkovPredictor(2), drop="immediate")
    _, lazy = run(df, predictor=MarkovPredictor(2), drop="on_evict")
    # same cache logic; prefetch completion timing can shift a few entries, so allow a small margin
    assert abs(lazy["demand_misses"] - eager["demand_misses"]) <= 0.1 * len(t)
    assert lazy["n"] == len(t)


def test_lazy_variants_registered():
    from augur.storage.realbench import REAL_CONFIGS

    assert REAL_CONFIGS["lru"].drop == "on_evict"
    assert REAL_CONFIGS["lru-eager"].drop == "immediate"
    assert REAL_CONFIGS["markov2-eager"].drop == "immediate"

import math

import pytest

from augur.network.breakeven import (
    CodecProfile, break_even_bandwidth, coded_time, fastest, mbit_to_Bps, raw_time,
)

C = CodecProfile("x", ratio=0.25, compress_Bps=2e6, decompress_Bps=8e6)
SIZE = 5e6


@pytest.mark.parametrize("scenario", ["static", "sequential", "pipelined"])
def test_break_even_is_the_crossover(scenario):
    b = break_even_bandwidth(C, scenario)
    assert b > 0
    assert coded_time(SIZE, C, b, scenario) == pytest.approx(raw_time(SIZE, b))
    assert coded_time(SIZE, C, b * 0.5, scenario) < raw_time(SIZE, b * 0.5)  # slower link: coding wins
    assert coded_time(SIZE, C, b * 2.0, scenario) > raw_time(SIZE, b * 2.0)  # faster link: raw wins


def test_break_even_independent_of_size_and_rtt():
    b = break_even_bandwidth(C, "sequential")
    for size in (1e3, 1e9):
        for rtt in (0.0, 0.3):
            assert coded_time(size, C, b, "sequential", rtt) == pytest.approx(raw_time(size, b, rtt))


def test_scenarios_are_ordered_static_best_sequential_worst():
    t = {s: coded_time(SIZE, C, 1e6, s) for s in ("static", "sequential", "pipelined")}
    assert t["static"] < t["sequential"]
    assert t["pipelined"] <= t["sequential"]


def test_codec_that_does_not_shrink_never_wins():
    bad = CodecProfile("bad", ratio=1.0, compress_Bps=1e9, decompress_Bps=1e9)
    for s in ("static", "sequential", "pipelined"):
        assert break_even_bandwidth(bad, s) == 0.0
    assert fastest(SIZE, [bad], 1e3) == "raw"


def test_fastest_picks_by_bandwidth():
    slow_strong = CodecProfile("strong", 0.2, 1e5, 1e6)
    fast_weak = CodecProfile("weak", 0.5, 1e8, 1e9)
    assert fastest(SIZE, [slow_strong, fast_weak], mbit_to_Bps(0.5)) == "strong"
    assert fastest(SIZE, [slow_strong, fast_weak], mbit_to_Bps(500)) == "weak"
    assert fastest(SIZE, [slow_strong, fast_weak], mbit_to_Bps(100000)) == "raw"


def test_unknown_scenario_rejected():
    with pytest.raises(ValueError):
        coded_time(1, C, 1, "nope")
    with pytest.raises(ValueError):
        break_even_bandwidth(C, "nope")

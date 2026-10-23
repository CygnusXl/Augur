import pytest

from augur.traces import WORKLOADS


@pytest.mark.parametrize("name", list(WORKLOADS))
def test_deterministic_by_seed(name):
    a, b = WORKLOADS[name](800, 5), WORKLOADS[name](800, 5)
    assert a.accesses == b.accesses and a.sizes == b.sizes


@pytest.mark.parametrize("name", [n for n in WORKLOADS if n not in ("sequential", "dl_fixed_order")])
def test_different_seeds_differ(name):
    assert WORKLOADS[name](800, 1).accesses != WORKLOADS[name](800, 2).accesses


@pytest.mark.parametrize("name", list(WORKLOADS))
def test_trace_is_well_formed(name):
    t = WORKLOADS[name](800, 0)
    # DL traces are whole epochs, so their length rounds down to a multiple of the epoch count.
    assert 795 <= len(t.accesses) <= 800
    assert all(a in t.sizes for a in t.accesses)
    assert all(s > 0 for s in t.sizes.values())
    assert t.unique_items <= len(t.sizes)
    assert t.requested_bytes >= t.unique_bytes > 0

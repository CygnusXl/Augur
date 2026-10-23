import random

import pytest

from augur.core.cache import ByteCache


@pytest.mark.parametrize("policy", ["lru", "lfu"])
def test_capacity_never_exceeded_under_random_ops(policy):
    rng = random.Random(1)
    cache = ByteCache(10_000, policy)
    for _ in range(5000):
        k = rng.randrange(60)
        if rng.random() < 0.6:
            cache.put(k, rng.randint(1, 3000), prefetched=rng.random() < 0.5)
        elif rng.random() < 0.9:
            cache.get(k)
        else:
            cache.remove(k)
        assert cache.used_bytes <= cache.capacity
    cache.check_invariants()
    assert cache.peak_bytes <= cache.capacity


def test_lru_evicts_least_recently_used():
    c = ByteCache(300, "lru")
    for k in "abc":
        c.put(k, 100)
    c.get("a")  # b is now least recently used
    c.put("d", 100)
    assert "b" not in c and {"a", "c", "d"} <= {k for k, _ in c.entries()}


def test_lfu_evicts_least_frequently_used():
    c = ByteCache(300, "lfu")
    for k in "abc":
        c.put(k, 100)
    for _ in range(3):
        c.get("a")
        c.get("c")
    c.put("d", 100)
    assert "b" not in c and "a" in c and "c" in c and "d" in c


@pytest.mark.parametrize("policy", ["lru", "lfu"])
def test_oversize_item_rejected_and_cache_untouched(policy):
    c = ByteCache(100, policy)
    c.put("x", 60)
    assert c.put("big", 101) is False
    assert "big" not in c and "x" in c
    assert c.used_bytes == 60


def test_values_are_returned_byte_identical():
    c = ByteCache(1 << 20)
    payload = random.Random(3).randbytes(4096)
    c.put("f", len(payload), value=payload)
    assert c.get("f").value == payload
    assert c.peek("f").value is payload


def test_on_evict_called_with_entry():
    seen = []
    c = ByteCache(200, "lru", on_evict=lambda k, e: seen.append((k, e.size)))
    c.put(1, 100)
    c.put(2, 100)
    c.put(3, 100)
    assert seen == [(1, 100)]


def test_remove_does_not_call_on_evict_and_frees_bytes():
    seen = []
    c = ByteCache(200, on_evict=lambda k, e: seen.append(k))
    c.put(1, 150)
    assert c.remove(1).size == 150
    assert seen == [] and c.used_bytes == 0 and c.remove(1) is None


def test_replacing_key_updates_accounting():
    c = ByteCache(500)
    c.put("k", 100)
    c.put("k", 300)
    assert c.used_bytes == 300 and len(c) == 1
    c.check_invariants()


def test_peek_does_not_change_state():
    c = ByteCache(200, "lru")
    c.put(1, 100)
    c.put(2, 100)
    e = c.peek(1)
    assert not e.used and e.freq == 1
    c.put(3, 100)  # 1 is still least recent, so it is evicted
    assert 1 not in c


def test_get_marks_used_and_prefetch_flag_preserved():
    c = ByteCache(200)
    c.put(1, 50, prefetched=True)
    assert c.peek(1).prefetched and not c.peek(1).used
    c.get(1)
    assert c.peek(1).used


def test_invalid_arguments():
    with pytest.raises(ValueError):
        ByteCache(0)
    with pytest.raises(ValueError):
        ByteCache(10, "fifo")
    with pytest.raises(ValueError):
        ByteCache(10).put(1, 0)


def test_lfu_heap_stays_bounded():
    c = ByteCache(1000, "lfu")
    c.put(1, 10)
    for _ in range(10_000):
        c.get(1)
    assert len(c._heap) <= 4 * len(c) + 64 + 1

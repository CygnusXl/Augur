"""Byte-bounded cache with LRU or LFU eviction.

The cache stores whatever value it is given and returns it untouched, so a
real-I/O layer can keep file bytes in it and the original data is preserved
exactly. The simulator stores ``None`` and tracks sizes only.
"""

from __future__ import annotations

import heapq
from collections import OrderedDict
from typing import Any, Callable, Hashable, Iterator, Optional


class Entry:
    __slots__ = ("size", "value", "prefetched", "used", "freq", "tick")

    def __init__(self, size: int, value: Any, prefetched: bool, tick: int):
        self.size = size
        self.value = value
        self.prefetched = prefetched  # inserted by a prefetch, not a demand read
        self.used = False  # served at least one request since insertion
        self.freq = 1
        self.tick = tick


class ByteCache:
    """Cache bounded by total bytes, never by item count."""

    def __init__(
        self,
        capacity_bytes: int,
        policy: str = "lru",
        on_evict: Optional[Callable[[Hashable, Entry], None]] = None,
    ):
        if capacity_bytes <= 0:
            raise ValueError("capacity_bytes must be positive")
        if policy not in ("lru", "lfu"):
            raise ValueError(f"unknown policy {policy!r}")
        self.capacity = capacity_bytes
        self.policy = policy
        self.on_evict = on_evict
        self.used_bytes = 0
        self.peak_bytes = 0
        self._entries: "OrderedDict[Hashable, Entry]" = OrderedDict()
        self._heap: list = []  # LFU only: (freq, tick, key), lazily invalidated
        self._tick = 0

    # ---- read side -------------------------------------------------
    def __contains__(self, key: Hashable) -> bool:
        return key in self._entries

    def __len__(self) -> int:
        return len(self._entries)

    def peek(self, key: Hashable) -> Optional[Entry]:
        """Look up without changing recency, frequency or the used flag."""
        return self._entries.get(key)

    def get(self, key: Hashable) -> Optional[Entry]:
        """Look up as a real request: updates policy state and marks used."""
        entry = self._entries.get(key)
        if entry is None:
            return None
        entry.used = True
        self._touch(key, entry)
        return entry

    def entries(self) -> Iterator[tuple]:
        return iter(self._entries.items())

    # ---- write side ------------------------------------------------
    def put(self, key: Hashable, size: int, value: Any = None, prefetched: bool = False) -> bool:
        """Insert an item. Returns False if it can never fit (size > capacity)."""
        if size <= 0:
            raise ValueError("size must be positive")
        if key in self._entries:
            self.remove(key)
        if size > self.capacity:
            return False
        while self.used_bytes + size > self.capacity:
            self._evict_one()
        self._tick += 1
        entry = Entry(size, value, prefetched, self._tick)
        self._entries[key] = entry
        self.used_bytes += size
        if self.used_bytes > self.peak_bytes:
            self.peak_bytes = self.used_bytes
        if self.policy == "lfu":
            heapq.heappush(self._heap, (entry.freq, entry.tick, key))
        return True

    def remove(self, key: Hashable) -> Optional[Entry]:
        """Explicit removal; does not call on_evict."""
        entry = self._entries.pop(key, None)
        if entry is not None:
            self.used_bytes -= entry.size
        return entry

    # ---- internals -------------------------------------------------
    def _touch(self, key: Hashable, entry: Entry) -> None:
        self._tick += 1
        entry.tick = self._tick
        entry.freq += 1
        if self.policy == "lru":
            self._entries.move_to_end(key)
        else:
            heapq.heappush(self._heap, (entry.freq, entry.tick, key))
            if len(self._heap) > 4 * len(self._entries) + 64:
                self._heap = [(e.freq, e.tick, k) for k, e in self._entries.items()]
                heapq.heapify(self._heap)

    def _evict_one(self) -> None:
        if self.policy == "lru":
            key, entry = self._entries.popitem(last=False)
        else:
            while True:
                freq, tick, key = heapq.heappop(self._heap)
                entry = self._entries.get(key)
                if entry is not None and entry.freq == freq and entry.tick == tick:
                    break
            del self._entries[key]
        self.used_bytes -= entry.size
        if self.on_evict is not None:
            self.on_evict(key, entry)

    def check_invariants(self) -> None:
        """Raise AssertionError if byte accounting is inconsistent."""
        total = sum(e.size for e in self._entries.values())
        assert total == self.used_bytes, (total, self.used_bytes)
        assert self.used_bytes <= self.capacity, (self.used_bytes, self.capacity)

"""Prefetch scheduler: decides which predictions become reads.

It is deliberately separate from the predictor. A prediction is only a
suggestion; the scheduler enforces confidence, a cap on reads in flight, a
byte budget, and (optionally) backs off when recent prefetches were wasted.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Optional

from .predictors import Candidate

MiB = 1024 * 1024


@dataclass
class SchedulerConfig:
    threshold: float = 0.4  # minimum (cumulative) confidence to act on
    depth: int = 4  # candidates requested from the predictor, and max new reads per step
    max_inflight: int = 8  # reads in flight at once
    byte_budget: int = 8 * MiB  # bytes in flight at once
    adaptive: bool = False  # back off when recent prefetch accuracy is low
    window: int = 64
    min_samples: int = 16
    accuracy_floor: float = 0.2
    probe_every: int = 16  # while backed off, allow one probe prefetch this often


class PrefetchScheduler:
    def __init__(self, cfg: Optional[SchedulerConfig] = None):
        self.cfg = cfg or SchedulerConfig()
        self._outcomes: deque = deque(maxlen=self.cfg.window)
        self._calls = 0

    def record_outcome(self, useful: bool) -> None:
        """Feedback from the cache: a prefetch was used (True) or evicted unused (False)."""
        self._outcomes.append(1 if useful else 0)

    @property
    def rolling_accuracy(self) -> Optional[float]:
        if len(self._outcomes) < self.cfg.min_samples:
            return None
        return sum(self._outcomes) / len(self._outcomes)

    @property
    def backed_off(self) -> bool:
        acc = self.rolling_accuracy
        return self.cfg.adaptive and acc is not None and acc < self.cfg.accuracy_floor

    def select(
        self,
        candidates: Iterable[Candidate],
        is_cached: Callable[[int], bool],
        is_inflight: Callable[[int], bool],
        sizes: Dict[int, int],
        inflight_count: int,
        inflight_bytes: int,
    ) -> List[int]:
        cfg = self.cfg
        self._calls += 1
        limit = cfg.depth
        if self.backed_off:
            if self._calls % cfg.probe_every != 0:
                return []
            limit = 1
        chosen: List[int] = []
        seen = set()
        count, nbytes = inflight_count, inflight_bytes
        for cand in candidates:
            if len(chosen) >= limit:
                break
            item = cand.item
            if cand.confidence < cfg.threshold or item in seen or item not in sizes:
                continue
            if is_cached(item) or is_inflight(item):
                continue
            size = sizes[item]
            if count >= cfg.max_inflight or nbytes + size > cfg.byte_budget:
                break
            chosen.append(item)
            seen.add(item)
            count += 1
            nbytes += size
        return chosen

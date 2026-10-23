"""Next-access predictors.

Every predictor sees only the stream of item ids (``observe``) and returns up
to ``depth`` candidates with a confidence in [0, 1] (``predict``). Wrong
predictions are safe by construction: they only cost extra reads.

Frequency-based prediction is covered by LFU eviction in ``cache.py``. As a
prefetch predictor it would mostly name items that are already cached.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple


@dataclass(frozen=True)
class Candidate:
    item: int
    confidence: float


class Predictor:
    name = "none"

    def observe(self, item: int) -> None:
        pass

    def predict(self, depth: int) -> List[Candidate]:
        return []


class NoPredictor(Predictor):
    name = "none"


class SequentialPredictor(Predictor):
    """Conventional readahead: after a run of consecutive ids, fetch the next ones."""

    name = "sequential"

    def __init__(self, min_run: int = 2):
        self.min_run = min_run
        self._prev: int | None = None
        self._run = 0

    def observe(self, item: int) -> None:
        if self._prev is not None and item == self._prev + 1:
            self._run += 1
        else:
            self._run = 1
        self._prev = item

    def predict(self, depth: int) -> List[Candidate]:
        if self._prev is None or self._run < self.min_run:
            return []
        return [Candidate(self._prev + j, 1.0) for j in range(1, depth + 1)]


class StridePredictor(Predictor):
    """Constant-stride detector; confidence grows with the length of the streak."""

    name = "stride"

    def __init__(self) -> None:
        self._prev: int | None = None
        self._stride: int | None = None
        self._streak = 0

    def observe(self, item: int) -> None:
        if self._prev is not None:
            stride = item - self._prev
            if stride == self._stride:
                self._streak += 1
            else:
                self._stride = stride
                self._streak = 0
        self._prev = item

    def predict(self, depth: int) -> List[Candidate]:
        if self._prev is None or not self._stride or self._streak < 1:
            return []
        conf = self._streak / (self._streak + 1.0)
        return [Candidate(self._prev + self._stride * j, conf) for j in range(1, depth + 1)]


class MarkovPredictor(Predictor):
    """Transition counts over the last ``order`` ids, with back-off to lower orders.

    ``predict`` follows the most likely successor ``depth`` steps ahead;
    confidence is the product of the transition probabilities along the chain.
    Learns online from the stream it observes.
    """

    def __init__(self, order: int = 1, min_support: int = 2, smoothing: float = 1.0, name: str | None = None):
        # A transition seen once has a raw frequency of 1.0, which is overconfident.
        # min_support and smoothing temper that; min_support=1, smoothing=0 is the naive version.
        if order < 1:
            raise ValueError("order must be >= 1")
        self.order = order
        self.min_support = min_support
        self.smoothing = smoothing
        self.name = name or f"markov{order}"
        self._tables: List[Dict[Tuple[int, ...], Dict[int, int]]] = [dict() for _ in range(order + 1)]
        self._hist: List[int] = []

    def observe(self, item: int) -> None:
        for o in range(1, self.order + 1):
            if len(self._hist) >= o:
                ctx = tuple(self._hist[-o:])
                nxt = self._tables[o].setdefault(ctx, {})
                nxt[item] = nxt.get(item, 0) + 1
        self._hist.append(item)
        if len(self._hist) > self.order:
            del self._hist[0]

    def _step(self, hist: Sequence[int]) -> Tuple[int, float] | None:
        for o in range(min(self.order, len(hist)), 0, -1):
            counts = self._tables[o].get(tuple(hist[-o:]))
            if not counts:
                continue
            total = sum(counts.values())
            if total < self.min_support:
                continue
            best = max(counts.items(), key=lambda kv: kv[1])
            return best[0], best[1] / (total + self.smoothing)
        return None

    def predict(self, depth: int) -> List[Candidate]:
        hist = list(self._hist)
        out: List[Candidate] = []
        conf = 1.0
        for _ in range(depth):
            step = self._step(hist)
            if step is None:
                break
            item, p = step
            conf *= p
            out.append(Candidate(item, conf))
            hist.append(item)
        return out


class OraclePredictor(Predictor):
    """Clairvoyant upper bound: reads the future from the trace itself.

    On a seeded shuffle, a loader that knows the seed can compute exactly this
    schedule, so it is also the bound for seed-derived prefetching.
    """

    name = "oracle"

    def __init__(self, accesses: Sequence[int]):
        self._acc = accesses
        self._pos = -1

    def observe(self, item: int) -> None:
        self._pos += 1

    def predict(self, depth: int) -> List[Candidate]:
        return [Candidate(x, 1.0) for x in self._acc[self._pos + 1 : self._pos + 1 + depth]]

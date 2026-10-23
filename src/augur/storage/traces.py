"""Seeded, reproducible access traces.

These are synthetic: each generator encodes my assumptions about what a
workload looks like. They are for comparing predictors under controlled
conditions, not evidence about any real application. The real-I/O stage
checks that conclusions survive contact with actual files.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from itertools import accumulate
from typing import Callable, Dict, List

KiB = 1024
MiB = 1024 * KiB
BLOCK = 128 * KiB


@dataclass
class Trace:
    name: str
    accesses: List[int]
    sizes: Dict[int, int]
    seed: int
    params: dict = field(default_factory=dict)

    def __len__(self) -> int:
        return len(self.accesses)

    @property
    def unique_items(self) -> int:
        return len(set(self.accesses))

    @property
    def unique_bytes(self) -> int:
        return sum(self.sizes[i] for i in set(self.accesses))

    @property
    def requested_bytes(self) -> int:
        return sum(self.sizes[i] for i in self.accesses)


def _block_sizes(n_items: int) -> Dict[int, int]:
    return {i: BLOCK for i in range(n_items)}


def _image_sizes(n_items: int, seed: int) -> Dict[int, int]:
    rng = random.Random(seed * 7919 + 13)
    return {i: rng.randint(60 * KiB, 160 * KiB) for i in range(n_items)}


def sequential(n: int, seed: int = 0) -> Trace:
    """Streaming through large files: consecutive blocks, once."""
    return Trace("sequential", list(range(n)), _block_sizes(n), seed, {"block": BLOCK})


def random_uniform(n: int, seed: int = 0, n_items: int | None = None) -> Trace:
    """Uniform random blocks: there is no pattern to learn."""
    n_items = n_items or n
    rng = random.Random(seed)
    acc = [rng.randrange(n_items) for _ in range(n)]
    return Trace("random", acc, _block_sizes(n_items), seed, {"n_items": n_items})


def zipf_working_set(n: int, seed: int = 0, n_items: int | None = None, alpha: float = 1.0) -> Trace:
    """Skewed reuse of a fixed set; item ids are shuffled so adjacency means nothing."""
    n_items = n_items or max(10, n // 4)
    rng = random.Random(seed)
    cum = list(accumulate(1.0 / (r ** alpha) for r in range(1, n_items + 1)))
    perm = list(range(n_items))
    rng.shuffle(perm)
    ranks = rng.choices(range(n_items), cum_weights=cum, k=n)
    acc = [perm[r] for r in ranks]
    return Trace("zipf_workingset", acc, _block_sizes(n_items), seed, {"alpha": alpha, "n_items": n_items})


def phased(n: int, seed: int = 0, phase_len: int | None = None, n_items: int | None = None) -> Trace:
    """Changing pattern: sequential, strided, recurring tour, random; cycled."""
    rng = random.Random(seed)
    n_items = n_items or n
    phase_len = phase_len or max(1, n // 8)
    tour = rng.sample(range(n_items), max(2, phase_len // 2))
    kinds = ["sequential", "strided", "recurring", "random"]
    acc: List[int] = []
    p = 0
    while len(acc) < n:
        kind = kinds[p % len(kinds)]
        start = rng.randrange(n_items)
        for i in range(phase_len):
            if kind == "sequential":
                x = (start + i) % n_items
            elif kind == "strided":
                x = (start + 7 * i) % n_items
            elif kind == "recurring":
                x = tour[i % len(tour)]
            else:
                x = rng.randrange(n_items)
            acc.append(x)
        p += 1
    return Trace("phased", acc[:n], _block_sizes(n_items), seed, {"phase_len": phase_len, "n_items": n_items})


def recurring_routines(
    n: int,
    seed: int = 0,
    n_items: int | None = None,
    n_routines: int = 8,
    routine_len: int = 250,
    noise: float = 0.03,
) -> Trace:
    """Irregular but recurring: a few fixed random routines, picked at random.

    This is the case the hypothesis targets (my construction, not a real
    application). Each routine is a random sequence, so stride and sequential
    detectors see nothing, but a history model can learn it.
    """
    rng = random.Random(seed)
    n_items = n_items or max(1000, n // 6)
    routines = [rng.sample(range(n_items), routine_len) for _ in range(n_routines)]
    acc: List[int] = []
    while len(acc) < n:
        routine = routines[rng.randrange(n_routines)]
        for x in routine:
            acc.append(rng.randrange(n_items) if rng.random() < noise else x)
    params = {"n_routines": n_routines, "routine_len": routine_len, "noise": noise, "n_items": n_items}
    return Trace("recurring_routines", acc[:n], _block_sizes(n_items), seed, params)


def dl_batches(n: int, seed: int = 0, reshuffle: bool = True, epochs: int = 3) -> Trace:
    """Image-dataset epochs. Reshuffled epochs follow a seed no history model sees;
    fixed-order epochs repeat the same permutation (e.g. a cached shuffle)."""
    n_images = max(1, n // epochs)
    rng = random.Random(seed)
    base = list(range(n_images))
    rng.shuffle(base)
    acc: List[int] = []
    for e in range(epochs):
        if reshuffle and e > 0:
            order = base[:]
            rng.shuffle(order)
        else:
            order = base
        acc.extend(order)
    name = "dl_reshuffled" if reshuffle else "dl_fixed_order"
    return Trace(name, acc, _image_sizes(n_images, seed), seed, {"epochs": epochs, "n_images": n_images})


WORKLOADS: Dict[str, Callable[[int, int], Trace]] = {
    "sequential": sequential,
    "random": random_uniform,
    "zipf_workingset": zipf_working_set,
    "phased": phased,
    "recurring_routines": recurring_routines,
    "dl_reshuffled": lambda n, seed: dl_batches(n, seed, reshuffle=True),
    "dl_fixed_order": lambda n, seed: dl_batches(n, seed, reshuffle=False),
}

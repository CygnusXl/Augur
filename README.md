# augur

> What if your computer already knew what you were about to read?

augur is an experiment, not a product. It asks one question and answers it with measurements:

**Can a learned predictor make data-intensive programs measurably faster by guessing which files, blocks or dataset samples will be requested next, and fetching them into a bounded cache before they are asked for?**

It does not assume the answer is yes, and it does not assume the idea is new. Operating systems already do readahead, and there is a body of prior work on learned and heuristic prefetching (see the feasibility report). The point here is to find out *where*, if anywhere, a learned layer beats those baselines once its CPU, memory and wasted-read costs are counted.

## Status

| Stage | What | State |
| --- | --- | --- |
| 1 | Device baseline (cold vs warm reads on your drive) | script ready, run it on your machine |
| 2 | Trace generators, byte-bounded cache, event simulator | done, tested |
| 3 | Heuristic predictors (sequential, stride, Markov) and confidence-gated scheduler | done, tested |
| 4 | Real-I/O harness (thread-pool prefetcher, checksum-verified reads) | not started |
| 5 | Small learned model (MLP/GRU), inference cost timed separately | not started |
| 6 | Real image-dataset loading workload | not started |
| 7 | Ablations and final report | not started |

## Quick start

```bash
pip install -e ".[dev]"      # no runtime dependencies; pytest only for tests
pytest                        # 80 tests: cache correctness, bad predictions, memory limits
python scripts/device_baseline.py --dir /path/on/your/drive --size-mib 1024
python -m augur.bench --device sata_ssd --seeds 3 --out results
```

`python -m augur.bench --help` lists options (device model, cache fraction, think time, prefetch depth and threshold, workloads, configurations).

## Layout

```
src/augur/
  traces.py      reproducible seeded workloads
  cache.py       byte-bounded LRU/LFU cache; stores values untouched
  predictors.py  sequential, stride, Markov (order-k, back-off), clairvoyant oracle
  scheduler.py   confidence threshold, in-flight and byte caps, optional back-off
  simulator.py   trace-driven simulator with one FIFO storage device
  bench.py       workloads x configurations x seeds, identical conditions
tests/           pytest suite
scripts/         device_baseline.py
results/         reference summaries (simulated)
```

## Read this before trusting any number

- **The results in `results/` are simulated.** The device profiles (`hdd`, `sata_ssd`, `nvme`) are nominal order-of-magnitude assumptions, not measurements of any drive. The simulator ignores the OS page cache and parallel I/O queues. Treat rankings as hypotheses for the real-I/O stage, not as findings.
- **Outcomes depend on think time versus device speed.** With the default 100 us of compute between requests, prefetching helps on the NVMe and SATA models and *hurts* on the HDD model (reads are far slower than the compute they could overlap with, so extra reads only add contention). Change `--think-us` and the picture changes.
- **The "recurring routines" workload is my construction** to test the niche where history-based prediction should help. It is not a recording of any real application.
- **Frequency-based prediction is covered by LFU eviction**, not implemented as a prefetch predictor, because it would mostly name items that are already cached.
- The oracle predictor is an upper bound (it reads the future from the trace), not a deployable method.

## Simulated results so far (3 seeds, 20k accesses, cache = 5% of data, sata_ssd model)

Speedup is end-to-end time versus an LRU cache with no prefetching.

| workload | sequential | stride | markov2 | markov2+gate | oracle |
| --- | ---: | ---: | ---: | ---: | ---: |
| sequential | 1.38x | 1.38x | 1.00x | 1.00x | 1.38x |
| random | 1.00x | 1.00x | 1.00x | 1.00x | 1.28x |
| zipf working set | 1.00x | 1.00x | 1.00x | 1.00x | 1.50x |
| phased | 1.06x | 1.13x | 0.99x | 1.02x | 1.30x |
| recurring routines | 1.00x | 1.00x | 1.08x | 1.10x | 1.28x |
| DL, reshuffled each epoch | 1.00x | 1.00x | 1.00x | 1.00x | 1.31x |
| DL, fixed order | 1.00x | 1.00x | 1.09x | 1.09x | 1.31x |

What this suggests, to be confirmed on real I/O:

1. Conventional readahead already captures the sequential case; a learned model adds nothing there.
2. A history-based predictor only helps when history repeats (routines, fixed-order epochs). On random and freshly reshuffled access it has nothing to learn.
3. Accuracy is not speed. In `recurring_routines` Markov reaches 85% accuracy but only ~1.08x, and its P99 latency is far worse than LRU's because wasted prefetches queue ahead of real requests.
4. Trusting a single observation is dangerous. The `markov2-naive` ablation (one sighting = full confidence) falls to 0.36x on reshuffled data. The shipped default requires two observations and smooths confidence, at the cost of learning more slowly (compare `dl_fixed_order`: 1.09x default versus 1.19x naive over only three epochs).
5. A confidence gate that backs off when recent prefetches go to waste is cheap insurance.

Full tables: `results/summary_sata_ssd.md`, `summary_hdd.md`, `summary_nvme.md`.

## Roadmap

Real-I/O harness with cold-cache control (`posix_fadvise(DONTNEED)` is advisory; `O_DIRECT` where needed) and checksum verification of every served byte; a small learned model trained offline on a trace prefix with inference time reported separately; a PyTorch `DataLoader` workload on a real image set; ablations; and an honest verdict on whether the learned layer earns its complexity.

## Limitations and known failure cases

Single-process, single-device model; no kernel integration; Markov tables grow with distinct contexts (no eviction of model state yet); online learning only; traces are synthetic until stage 6.

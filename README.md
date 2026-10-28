# augur

> What if your computer already knew what you were about to read?

augur is a research testbed, not a product. It asks one question and answers it with measurements:

**Does predicting data make it faster to store and move?**

It studies two kinds of prediction under one framework: predicting *which item is requested next* (so it can be prefetched into a bounded cache), and predicting *the content of the data itself* (so a sender and receiver that share a model only transmit the surprises). It does not assume the answer is yes, and it does not claim the ideas are new: prefetching, learned caching and model-based compression are all established. See the paper for related work.

**Paper:** [`paper/augur.pdf`](paper/augur.pdf) (IEEE conference format; LaTeX source in `paper/`).

## What the measurements say so far

Measured on one machine (2 virtual CPUs); speeds are relative, sizes are exact. Every output was decoded and checked byte for byte.

- **Prediction makes data smaller.** `augur-cm`, a small exact context-mixing codec, produced the smallest output on 6 of 7 compressible real files: 6.8–31.5 % smaller than the best of gzip, bzip2, xz, zstd and brotli. On one executable xz was 5.2 % smaller. Random and already-compressed data cannot be shrunk; the codec stores them raw at a cost of one byte.
- **It does not (yet) make transfer faster.** `augur-cm` decodes at about 0.5 MB/s, over a thousand times slower than zstd. It is the fastest option on a link only below roughly 0.04–0.11 Mbit/s, and would need 16–53× faster decoding to win at 2 Mbit/s.
- **Simulated prefetching helps only where history repeats** (1.08–1.10× for the default Markov predictor on recurring access; none on random or reshuffled access), and trusting single observations can slow a workload to 0.36×. These storage results are simulated with nominal device parameters, not measured on a real drive.
- **Real reads on a hard disk agree that access prediction barely pays.** With a cold cache at every run, a learned Markov predictor gained at most 1.02-1.03x where the access order repeats exactly and ran at 0.94x on noisy recurring routines (28 % more data read), while a perfect predictor would reach 1.21-1.31x on the non-sequential workloads. Kernel readahead already handles sequential access. See `results/real/README.md` and `results/real/final-default-design/analysis.md`; one machine, synthetic access orders, three repeats.

Full tables: [`results/content/compression.md`](results/content/compression.md), [`ablation.md`](results/content/ablation.md), [`breakeven.md`](results/content/breakeven.md), and the storage summaries in `results/`.

## Quick start

```bash
pip install -e ".[dev,bench]"    # pytest, zstandard, brotli; the codec needs a C compiler (cc)
pytest                           # 112 tests

# Content domain: build the corpus, then compare codecs
python scripts/build_corpus.py --out data
python -m augur.content.bench  --corpus data/test --out results/content
python -m augur.content.ablate --corpus data/test --out results/content

# Storage domain: simulated prefetching experiments
python -m augur.storage.bench --device sata_ssd --seeds 3 --out results

# Real drive: check that cold reads can be forced before trusting any I/O result
python scripts/device_baseline.py --dir /path/on/your/drive --size-mib 1024

# Real drive: replay the workloads with real reads (cold cache every run)
python -m augur.storage.realbench --dir /path/on/your/drive --label mypc --repeats 1   # quick first look
python -m augur.storage.realbench --dir /path/on/your/drive --label mypc               # 3 repeats (about an hour on a hard disk)

# Regenerate the paper's tables and figures from the results, then build it
pip install -e ".[paper]" && python scripts/make_paper_artifacts.py
cd paper && latexmk -pdf augur.tex
```

## Layout

```
src/augur/
  core/      byte-bounded cache, predictors (sequential, stride, Markov, oracle), scheduler
  storage/   seeded access traces, trace-driven simulator, benchmark runner
  content/   augur_cm.c exact predictive codec, Python binding, corpus benchmark, ablations
  network/   closed-form model of when coding beats sending raw bytes
tests/       pytest suite (cache correctness, bad predictions, memory limits, codec round trips)
scripts/     build_corpus.py, device_baseline.py, make_paper_artifacts.py
paper/       IEEE-format paper, generated tables and figures, bibliography
results/     measured and simulated results
```

## Read this before trusting any number

- The **simulated storage results** (`results/summary_*.md`) use nominal device profiles (`hdd`, `sata_ssd`, `nvme`) and ignore the OS page cache and parallel I/O queues. The **real-I/O harness** (`augur.storage.realbench`) performs real reads, but the access orders are still synthetic and the kernel page cache is emulated as bounded (see the module docstring). Run it on your own drive; results are not portable.
- The **content results are measured**, but on one shared virtual machine with files of at most 1 MiB, including machine-local files. The corpus is not committed; `scripts/build_corpus.py` rebuilds it and writes a SHA-256 manifest. Gains on other data may differ.
- `augur-cm` is a small, unoptimized model in the lpaq family. It was not compared against PAQ8, cmix or NNCP, so nothing here claims to beat the state of the art.
- The **learned neural predictor** from the original plan has not been built. Only heuristic, Markov and context-mixing predictors are evaluated.
- The "recurring routines" workload is our own construction, not a recording of a real application.
- Network-transfer numbers come from a closed-form model fed with measured ratios and speeds. They ignore TCP dynamics, loss and parallel connections. No server-push or client-hint protocol has been built.

## Roadmap

An optimized and chunk-parallel codec; a small neural byte predictor with inference cost reported separately; a network study of server-side prediction with client budget hints; a real image-dataset loading workload.

## Licence

The code in this repository is released under the [MIT License](LICENSE). The paper text and figures in `paper/` are not covered by it; all rights are reserved by the author unless a separate licence is stated when the paper is posted.

`paper/IEEEtran.cls` and `paper/IEEEtran.bst` are the unmodified IEEE LaTeX class and style (LPPL), not part of this project's code.

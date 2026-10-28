<!-- Peter's workstation, one repeat per cell (--repeats 1). Differences under ~5% are not yet distinguishable from noise. Only the summary table was available (no runs.csv). -->
# Real-I/O results: peter-pc

Machine: Linux-7.0.0-38-generic-x86_64-with-glibc2.43, 16 CPUs, 61.3 GiB RAM, Python 3.14.4. Files on `ext4`, drive reported as **rotational (HDD)**.

1 repeats per cell (median shown; time column also shows min-max), 6000 accesses per workload, application cache = 5% of unique bytes, think time 1000 us, prefetch depth 4, threshold 0.4, 4 prefetch threads. Every run started with the file evicted from the page cache.

Cold/warm calibration (random reads on each data file; a ratio below 1.5 means results are unreliable): recurring_routines 744x, dl_fixed_order 956x, dl_reshuffled 608x, sequential 736x, random 604x.

Access orders are synthetic; reads, caches, CPU and memory are real. `speedup` is end-to-end time versus the named baseline (above 1.0 is faster). `device MiB` is what the kernel actually read from the device (readahead included). `cpu` is process CPU time over wall time. `RSS+` is extra peak resident memory.

## recurring_routines

| config | mean us | p95 us | p99 us | hit | accuracy | wasted MiB | device MiB | cpu | RSS+ MiB | predictor ms | time s (min-max) | vs os-default | vs lru |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| os-default | 9082 | 17916 | 39065 | - | - | 0.0 | 765.6 | 1% | 0.0 | 0.0 | 61.06 (61.06-61.06) | 1.00x | 1.07x |
| os-noreadahead | 9765 | 14509 | 36732 | - | - | 0.0 | 744.4 | 2% | 0.1 | 0.0 | 65.19 (65.19-65.19) | 0.94x | 1.00x |
| lru | 9825 | 15494 | 38135 | 1% | - | 0.0 | 759.8 | 1% | 6.0 | 0.0 | 65.33 (65.33-65.33) | 0.93x | 1.00x |
| sequential | 9650 | 14700 | 35882 | 1% | 0% | 0.5 | 760.2 | 1% | 6.4 | 8.8 | 64.35 (64.35-64.35) | 0.95x | 1.02x |
| markov2 | 10576 | 29104 | 52824 | 34% | 57% | 192.8 | 932.5 | 2% | 10.8 | 151.7 | 70.19 (70.19-70.19) | 0.87x | 0.93x |
| oracle | 6202 | 29200 | 42334 | 100% | 100% | 0.0 | 703.3 | 3% | 6.4 | 36.2 | 43.85 (43.85-43.85) | 1.39x | 1.49x |

## dl_fixed_order

| config | mean us | p95 us | p99 us | hit | accuracy | wasted MiB | device MiB | cpu | RSS+ MiB | predictor ms | time s (min-max) | vs os-default | vs lru |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| os-default | 7749 | 20902 | 39790 | - | - | 0.0 | 690.9 | 2% | 0.0 | 0.0 | 53.07 (53.07-53.07) | 1.00x | 1.18x |
| os-noreadahead | 9587 | 14405 | 33056 | - | - | 0.0 | 623.5 | 2% | 0.0 | 0.0 | 64.13 (64.13-64.13) | 0.83x | 0.98x |
| lru | 9376 | 14381 | 29873 | 0% | - | 0.0 | 627.8 | 1% | 10.8 | 0.0 | 62.70 (62.70-62.70) | 0.85x | 1.00x |
| sequential | 9222 | 14330 | 29812 | 0% | 0% | 1.3 | 630.9 | 2% | 11.2 | 10.3 | 61.83 (61.83-61.83) | 0.86x | 1.01x |
| markov2 | 9056 | 14981 | 35513 | 33% | 100% | 0.3 | 629.4 | 2% | 19.3 | 102.8 | 60.97 (60.97-60.97) | 0.87x | 1.03x |
| oracle | 6923 | 29759 | 42150 | 100% | 100% | 0.0 | 632.0 | 3% | 12.6 | 36.4 | 48.18 (48.18-48.18) | 1.10x | 1.30x |

## dl_reshuffled

| config | mean us | p95 us | p99 us | hit | accuracy | wasted MiB | device MiB | cpu | RSS+ MiB | predictor ms | time s (min-max) | vs os-default | vs lru |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| os-default | 7767 | 20793 | 40144 | - | - | 0.0 | 708.3 | 1% | 0.0 | 0.0 | 53.16 (53.16-53.16) | 1.00x | 1.20x |
| os-noreadahead | 9806 | 14842 | 33897 | - | - | 0.0 | 623.1 | 1% | 0.0 | 0.0 | 65.43 (65.43-65.43) | 0.81x | 0.98x |
| lru | 9594 | 14709 | 30274 | 0% | - | 0.0 | 626.2 | 1% | 11.2 | 0.0 | 63.98 (63.98-63.98) | 0.83x | 1.00x |
| sequential | 9563 | 14845 | 32998 | 0% | 0% | 0.4 | 629.6 | 1% | 11.2 | 9.2 | 63.86 (63.86-63.86) | 0.83x | 1.00x |
| markov2 | 9719 | 14965 | 33337 | 0% | - | 0.0 | 626.2 | 2% | 12.6 | 108.2 | 64.89 (64.89-64.89) | 0.82x | 0.99x |
| oracle | 6905 | 29329 | 40006 | 100% | 100% | 0.0 | 629.8 | 2% | 12.6 | 34.2 | 48.06 (48.06-48.06) | 1.11x | 1.33x |

## sequential

| config | mean us | p95 us | p99 us | hit | accuracy | wasted MiB | device MiB | cpu | RSS+ MiB | predictor ms | time s (min-max) | vs os-default | vs lru |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| os-default | 538 | 129 | 17723 | - | - | 0.0 | 750.0 | 4% | 0.0 | 0.0 | 9.70 (9.70-9.70) | 1.00x | 0.96x |
| os-noreadahead | 802 | 811 | 1220 | - | - | 0.0 | 750.0 | 6% | 0.0 | 0.0 | 11.32 (11.32-11.32) | 0.86x | 0.82x |
| lru | 488 | 136 | 18519 | 0% | - | 0.0 | 750.0 | 4% | 37.1 | 0.0 | 9.31 (9.31-9.31) | 1.04x | 1.00x |
| sequential | 518 | 18 | 17675 | 100% | 100% | 0.0 | 750.0 | 10% | 38.3 | 41.4 | 9.81 (9.81-9.81) | 0.99x | 0.95x |
| markov2 | 593 | 79 | 25980 | 0% | - | 0.0 | 750.0 | 4% | 39.3 | 36.2 | 10.00 (10.00-10.00) | 0.97x | 0.93x |
| oracle | 430 | 17 | 25500 | 100% | 100% | 0.0 | 750.0 | 10% | 38.2 | 41.3 | 9.29 (9.29-9.29) | 1.04x | 1.00x |

## random

| config | mean us | p95 us | p99 us | hit | accuracy | wasted MiB | device MiB | cpu | RSS+ MiB | predictor ms | time s (min-max) | vs os-default | vs lru |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| os-default | 9685 | 14913 | 32107 | - | - | 0.0 | 728.5 | 1% | 0.0 | 0.0 | 64.67 (64.67-64.67) | 1.00x | 1.03x |
| os-noreadahead | 9596 | 14825 | 29512 | - | - | 0.0 | 724.2 | 1% | 0.0 | 0.0 | 64.14 (64.14-64.14) | 1.01x | 1.04x |
| lru | 10042 | 15416 | 37504 | 3% | - | 0.0 | 729.0 | 1% | 23.0 | 0.0 | 66.69 (66.69-66.69) | 0.97x | 1.00x |
| sequential | 9710 | 15253 | 33622 | 3% | 0% | 1.5 | 733.6 | 1% | 23.1 | 9.0 | 64.70 (64.70-64.70) | 1.00x | 1.03x |
| markov2 | 9717 | 15097 | 32058 | 3% | - | 0.0 | 729.0 | 2% | 23.9 | 74.0 | 64.83 (64.83-64.83) | 1.00x | 1.03x |
| oracle | 7046 | 30912 | 41487 | 100% | 100% | 0.0 | 728.5 | 2% | 25.9 | 32.5 | 48.88 (48.88-48.88) | 1.32x | 1.36x |


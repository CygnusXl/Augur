# Real-I/O results: peter-pc-lazy

Machine: Linux-7.0.0-38-generic-x86_64-with-glibc2.43, 16 CPUs, 61.3 GiB RAM, Python 3.14.4. Files on `ext4`, drive reported as **rotational (HDD)**.

2 repeats per cell (median shown; time column also shows min-max), 6000 accesses per workload, application cache = 5% of unique bytes, think time 1000 us, prefetch depth 4, threshold 0.4, 4 prefetch threads. Every run started with the file evicted from the page cache.

Cold/warm calibration (random reads on each data file; a ratio below 1.5 means results are unreliable): dl_fixed_order 1374x, recurring_routines 767x.

Access orders are synthetic; reads, caches, CPU and memory are real. `speedup` is end-to-end time versus the named baseline (above 1.0 is faster). `device MiB` is what the kernel actually read from the device (readahead included). `cpu` is process CPU time over wall time. `RSS+` is extra peak resident memory.

## dl_fixed_order

| config | mean us | p95 us | p99 us | hit | accuracy | wasted MiB | device MiB | cpu | RSS+ MiB | predictor ms | time s (min-max) | vs os-default | vs lru |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| os-default | 10476 | 27038 | 50508 | - | - | 0.0 | 690.9 | 1% | 0.0 | 0.0 | 69.41 (68.72-70.10) | 1.00x | 1.23x |
| lru | 13115 | 22517 | 40181 | 0% | - | 0.0 | 627.8 | 1% | 7.1 | 0.0 | 85.11 (84.66-85.56) | 0.82x | 1.00x |
| lru-lazy | 10394 | 26149 | 48650 | 0% | - | 0.0 | 690.9 | 1% | 7.1 | 0.0 | 68.85 (68.48-69.22) | 1.01x | 1.24x |
| markov2 | 12718 | 24009 | 40241 | 33% | 100% | 0.3 | 628.9 | 1% | 18.9 | 96.9 | 82.91 (81.71-84.10) | 0.84x | 1.03x |
| markov2-lazy | 10168 | 27259 | 50058 | 33% | 100% | 0.3 | 691.2 | 2% | 16.6 | 95.5 | 67.64 (66.31-68.97) | 1.03x | 1.26x |
| markov2+gate | 12495 | 22296 | 35562 | 33% | 100% | 0.3 | 629.4 | 2% | 17.1 | 94.0 | 81.72 (81.17-82.26) | 0.85x | 1.04x |
| oracle-lazy | 8622 | 39001 | 63024 | 100% | 100% | 0.0 | 700.3 | 2% | 12.7 | 38.6 | 58.52 (58.17-58.87) | 1.19x | 1.45x |

## recurring_routines

| config | mean us | p95 us | p99 us | hit | accuracy | wasted MiB | device MiB | cpu | RSS+ MiB | predictor ms | time s (min-max) | vs os-default | vs lru |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| os-default | 9073 | 16104 | 36632 | - | - | 0.0 | 765.6 | 1% | 0.0 | 0.0 | 61.00 (60.54-61.46) | 1.00x | 1.05x |
| lru | 9644 | 14656 | 34209 | 1% | - | 0.0 | 759.8 | 1% | 1.3 | 0.0 | 64.25 (63.41-65.08) | 0.95x | 1.00x |
| lru-lazy | 9231 | 16607 | 39625 | 1% | - | 0.0 | 765.6 | 1% | 1.4 | 0.0 | 61.77 (61.35-62.18) | 0.99x | 1.04x |
| markov2 | 10506 | 27831 | 49126 | 34% | 57% | 192.1 | 932.7 | 2% | 6.1 | 112.2 | 69.65 (68.93-70.36) | 0.88x | 0.92x |
| markov2-lazy | 9601 | 28195 | 53179 | 34% | 57% | 187.8 | 984.2 | 2% | 5.8 | 107.5 | 64.26 (63.98-64.53) | 0.95x | 1.00x |
| markov2+gate | 9509 | 21365 | 38214 | 23% | 77% | 50.1 | 794.9 | 2% | 5.8 | 108.8 | 63.62 (62.54-64.70) | 0.96x | 1.01x |
| oracle-lazy | 6314 | 29617 | 46625 | 100% | 100% | 0.0 | 770.1 | 3% | 6.5 | 34.1 | 44.52 (44.23-44.82) | 1.37x | 1.44x |


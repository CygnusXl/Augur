# Real-I/O results: peter-pc-3rep

Machine: Linux-7.0.0-38-generic-x86_64-with-glibc2.43, 16 CPUs, 61.3 GiB RAM, Python 3.14.4. Files on `ext4`, drive reported as **rotational (HDD)**.

3 repeats per cell (median shown; time column also shows min-max), 6000 accesses per workload, application cache = 5% of unique bytes, think time 1000 us, prefetch depth 4, threshold 0.4, 4 prefetch threads. Every run started with the file evicted from the page cache.

Cold/warm calibration (random reads on each data file; a ratio below 1.5 means results are unreliable): recurring_routines 699x, dl_fixed_order 621x, dl_reshuffled 1001x, sequential 704x, random 827x.

Access orders are synthetic; reads, caches, CPU and memory are real. `speedup` is end-to-end time versus the named baseline (above 1.0 is faster). `device MiB` is what the kernel actually read from the device (readahead included). `cpu` is process CPU time over wall time. `RSS+` is extra peak resident memory.

## recurring_routines

| config | mean us | p95 us | p99 us | hit | accuracy | wasted MiB | device MiB | cpu | RSS+ MiB | predictor ms | time s (min-max) | vs os-default | vs lru |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| os-default | 8757 | 15416 | 34934 | - | - | 0.0 | 765.6 | 2% | 0.0 | 0.0 | 59.16 (58.85-59.17) | 1.00x | 1.06x |
| os-noreadahead | 9205 | 14288 | 27530 | - | - | 0.0 | 744.4 | 2% | 0.0 | 0.0 | 61.83 (61.47-62.79) | 0.96x | 1.01x |
| lru | 9382 | 14570 | 32068 | 1% | - | 0.0 | 759.8 | 2% | 5.8 | 0.0 | 62.67 (61.02-63.56) | 0.94x | 1.00x |
| sequential | 9150 | 14419 | 29648 | 1% | 0% | 0.5 | 760.2 | 2% | 6.1 | 9.6 | 61.39 (61.15-62.87) | 0.96x | 1.02x |
| markov2 | 9899 | 24967 | 42851 | 34% | 57% | 192.4 | 932.4 | 2% | 10.6 | 116.3 | 66.07 (64.71-67.41) | 0.90x | 0.95x |
| oracle | 6425 | 29167 | 44318 | 100% | 100% | 0.0 | 766.4 | 3% | 6.4 | 39.1 | 45.25 (44.22-45.82) | 1.31x | 1.38x |

## dl_fixed_order

| config | mean us | p95 us | p99 us | hit | accuracy | wasted MiB | device MiB | cpu | RSS+ MiB | predictor ms | time s (min-max) | vs os-default | vs lru |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| os-default | 7602 | 20490 | 37759 | - | - | 0.0 | 690.9 | 2% | 0.0 | 0.0 | 52.37 (51.06-52.98) | 1.00x | 1.20x |
| os-noreadahead | 9347 | 14269 | 29380 | - | - | 0.0 | 623.5 | 2% | 0.0 | 0.0 | 62.90 (62.24-63.67) | 0.83x | 1.00x |
| lru | 9395 | 14408 | 30703 | 0% | - | 0.0 | 627.8 | 2% | 11.0 | 0.0 | 63.05 (61.42-63.80) | 0.83x | 1.00x |
| sequential | 9229 | 14267 | 29592 | 0% | 0% | 1.3 | 631.3 | 2% | 11.0 | 10.6 | 61.89 (61.31-62.34) | 0.85x | 1.02x |
| markov2 | 8885 | 14191 | 28848 | 33% | 100% | 0.3 | 629.4 | 2% | 20.4 | 95.1 | 60.19 (59.83-61.88) | 0.87x | 1.05x |
| oracle | 6524 | 29274 | 40532 | 100% | 100% | 0.0 | 642.4 | 3% | 12.8 | 46.6 | 45.85 (45.33-46.07) | 1.14x | 1.38x |

## dl_reshuffled

| config | mean us | p95 us | p99 us | hit | accuracy | wasted MiB | device MiB | cpu | RSS+ MiB | predictor ms | time s (min-max) | vs os-default | vs lru |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| os-default | 7288 | 18072 | 35039 | - | - | 0.0 | 708.3 | 2% | 0.0 | 0.0 | 50.34 (50.31-50.60) | 1.00x | 1.24x |
| os-noreadahead | 9155 | 14186 | 26835 | - | - | 0.0 | 623.1 | 2% | 0.0 | 0.0 | 61.57 (61.52-62.08) | 0.82x | 1.01x |
| lru | 9294 | 14315 | 32765 | 0% | - | 0.0 | 626.2 | 2% | 11.3 | 0.0 | 62.21 (61.83-62.80) | 0.81x | 1.00x |
| sequential | 9208 | 14329 | 29765 | 0% | 0% | 0.4 | 629.6 | 2% | 11.4 | 10.5 | 61.77 (60.86-63.03) | 0.81x | 1.01x |
| markov2 | 9145 | 14197 | 28611 | 0% | - | 0.0 | 626.2 | 2% | 12.5 | 96.9 | 61.47 (61.11-61.67) | 0.82x | 1.01x |
| oracle | 6622 | 28595 | 41029 | 100% | 100% | 0.0 | 630.3 | 3% | 13.1 | 38.2 | 46.42 (46.29-48.95) | 1.08x | 1.34x |

## sequential

| config | mean us | p95 us | p99 us | hit | accuracy | wasted MiB | device MiB | cpu | RSS+ MiB | predictor ms | time s (min-max) | vs os-default | vs lru |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| os-default | 443 | 57 | 18941 | - | - | 0.0 | 750.0 | 3% | 0.0 | 0.0 | 9.12 (9.10-9.36) | 1.00x | 0.96x |
| os-noreadahead | 726 | 818 | 1386 | - | - | 0.0 | 750.0 | 7% | 0.0 | 0.0 | 10.96 (10.83-11.33) | 0.83x | 0.80x |
| lru | 383 | 113 | 16282 | 0% | - | 0.0 | 750.0 | 4% | 37.1 | 0.0 | 8.74 (8.36-8.74) | 1.04x | 1.00x |
| sequential | 378 | 10 | 17153 | 100% | 100% | 0.0 | 750.0 | 8% | 38.3 | 34.6 | 8.94 (8.63-9.04) | 1.02x | 0.98x |
| markov2 | 396 | 103 | 16665 | 0% | - | 0.0 | 750.0 | 5% | 38.6 | 38.1 | 8.86 (8.76-9.30) | 1.03x | 0.99x |
| oracle | 429 | 9 | 23289 | 100% | 100% | 0.0 | 750.0 | 7% | 38.0 | 31.9 | 9.22 (9.00-9.45) | 0.99x | 0.95x |

## random

| config | mean us | p95 us | p99 us | hit | accuracy | wasted MiB | device MiB | cpu | RSS+ MiB | predictor ms | time s (min-max) | vs os-default | vs lru |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| os-default | 9644 | 14912 | 32481 | - | - | 0.0 | 728.5 | 2% | 0.0 | 0.0 | 64.47 (63.34-64.84) | 1.00x | 0.99x |
| os-noreadahead | 9535 | 14737 | 28581 | - | - | 0.0 | 724.2 | 2% | 0.0 | 0.0 | 63.83 (63.35-64.10) | 1.01x | 1.00x |
| lru | 9573 | 14887 | 29527 | 3% | - | 0.0 | 729.0 | 1% | 22.9 | 0.0 | 63.87 (63.34-66.87) | 1.01x | 1.00x |
| sequential | 9585 | 14938 | 32077 | 3% | 0% | 1.5 | 734.9 | 2% | 23.0 | 9.6 | 64.03 (63.75-64.27) | 1.01x | 1.00x |
| markov2 | 9480 | 14775 | 26208 | 3% | - | 0.0 | 729.0 | 2% | 23.6 | 70.9 | 63.44 (63.39-63.79) | 1.02x | 1.01x |
| oracle | 7066 | 30754 | 42848 | 100% | 100% | 0.0 | 727.9 | 3% | 26.5 | 36.9 | 49.09 (48.89-49.62) | 1.31x | 1.30x |


<!-- Default design (kernel keeps an item until the application cache evicts it), 3 repeats. Several runs were disturbed by something else using the drive; see analysis.md. -->
# Real-I/O results: peter-pc-final

Machine: Linux-7.0.0-38-generic-x86_64-with-glibc2.43, 16 CPUs, 61.3 GiB RAM, Python 3.14.4. Files on `ext4`, drive reported as **rotational (HDD)**.

3 repeats per cell (median shown; time column also shows min-max), 6000 accesses per workload, application cache = 5% of unique bytes, think time 1000 us, prefetch depth 4, threshold 0.4, 4 prefetch threads. Every run started with the file evicted from the page cache.

Cold/warm calibration (random reads on each data file; a ratio below 1.5 means results are unreliable): recurring_routines 620x, dl_fixed_order 856x, dl_reshuffled 983x, sequential 851x, random 592x.

Access orders are synthetic; reads, caches, CPU and memory are real. `speedup` is end-to-end time versus the named baseline (above 1.0 is faster). `device MiB` is what the kernel actually read from the device (readahead included). `cpu` is process CPU time over wall time. `RSS+` is extra peak resident memory.

## recurring_routines

| config | mean us | p95 us | p99 us | hit | accuracy | wasted MiB | device MiB | cpu | RSS+ MiB | predictor ms | time s (min-max) | vs os-default | vs lru |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| os-default | 9513 | 22481 | 48117 | - | - | 0.0 | 765.6 | 1% | 0.1 | 0.0 | 63.65 (59.43-195.69) | 1.00x | 0.94x |
| os-noreadahead | 9531 | 14465 | 34488 | - | - | 0.0 | 744.4 | 1% | 0.0 | 0.0 | 63.73 (62.79-64.84) | 1.00x | 0.94x |
| lru | 8897 | 16147 | 35417 | 1% | - | 0.0 | 765.6 | 1% | 5.8 | 0.0 | 59.76 (59.47-61.07) | 1.07x | 1.00x |
| sequential | 9482 | 19913 | 46512 | 1% | 0% | 0.5 | 766.1 | 1% | 6.0 | 11.9 | 63.39 (61.02-199.42) | 1.00x | 0.94x |
| markov2 | 9436 | 27015 | 53583 | 34% | 57% | 190.6 | 981.0 | 2% | 10.7 | 86.4 | 63.22 (62.82-65.01) | 1.01x | 0.95x |
| markov2+gate | 9177 | 21850 | 41420 | 23% | 77% | 49.8 | 820.5 | 2% | 10.7 | 89.3 | 61.60 (61.49-62.91) | 1.03x | 0.97x |
| oracle | 6621 | 31061 | 51626 | 100% | 100% | 0.0 | 791.6 | 2% | 6.5 | 33.9 | 46.36 (46.29-122.19) | 1.37x | 1.29x |

## dl_fixed_order

| config | mean us | p95 us | p99 us | hit | accuracy | wasted MiB | device MiB | cpu | RSS+ MiB | predictor ms | time s (min-max) | vs os-default | vs lru |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| os-default | 8011 | 22391 | 42208 | - | - | 0.0 | 690.9 | 2% | 0.0 | 0.0 | 54.83 (52.62-55.15) | 1.00x | 0.97x |
| os-noreadahead | 9805 | 14605 | 32567 | - | - | 0.0 | 623.5 | 2% | 0.0 | 0.0 | 65.65 (64.62-66.00) | 0.84x | 0.81x |
| lru | 7790 | 19689 | 40053 | 0% | - | 0.0 | 690.9 | 2% | 11.0 | 0.0 | 53.37 (53.02-93.36) | 1.03x | 1.00x |
| sequential | 7806 | 19883 | 38268 | 0% | 0% | 1.3 | 690.3 | 2% | 11.0 | 9.7 | 53.54 (52.22-163.25) | 1.02x | 1.00x |
| markov2 | 7529 | 19680 | 41280 | 33% | 100% | 0.3 | 691.2 | 3% | 20.5 | 90.3 | 52.06 (51.91-52.64) | 1.05x | 1.03x |
| markov2+gate | 7491 | 19380 | 40719 | 33% | 100% | 0.3 | 691.2 | 2% | 19.4 | 90.6 | 51.84 (51.62-156.03) | 1.06x | 1.03x |
| oracle | 6239 | 30632 | 50459 | 100% | 100% | 0.0 | 700.3 | 3% | 13.0 | 43.8 | 44.38 (43.67-81.09) | 1.24x | 1.20x |

## dl_reshuffled

| config | mean us | p95 us | p99 us | hit | accuracy | wasted MiB | device MiB | cpu | RSS+ MiB | predictor ms | time s (min-max) | vs os-default | vs lru |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| os-default | 7763 | 20695 | 43148 | - | - | 0.0 | 708.3 | 1% | 0.0 | 0.0 | 53.11 (51.81-54.32) | 1.00x | 1.00x |
| os-noreadahead | 9402 | 14318 | 28197 | - | - | 0.0 | 623.1 | 2% | 0.0 | 0.0 | 63.24 (62.95-66.44) | 0.84x | 0.84x |
| lru | 7762 | 21213 | 38505 | 0% | - | 0.0 | 708.3 | 2% | 11.2 | 0.0 | 53.22 (52.15-53.78) | 1.00x | 1.00x |
| sequential | 7912 | 21798 | 42151 | 0% | 0% | 0.4 | 708.1 | 2% | 11.2 | 9.6 | 53.95 (51.73-54.64) | 0.98x | 0.99x |
| markov2 | 7874 | 22017 | 43301 | 0% | - | 0.0 | 708.3 | 2% | 12.1 | 116.7 | 53.82 (52.30-56.38) | 0.99x | 0.99x |
| markov2+gate | 7734 | 21876 | 41708 | 0% | - | 0.0 | 708.3 | 2% | 11.8 | 94.6 | 52.94 (52.28-55.56) | 1.00x | 1.01x |
| oracle | 6289 | 30357 | 51860 | 100% | 100% | 0.0 | 700.4 | 3% | 12.6 | 43.1 | 44.57 (43.85-46.07) | 1.19x | 1.19x |

## sequential

| config | mean us | p95 us | p99 us | hit | accuracy | wasted MiB | device MiB | cpu | RSS+ MiB | predictor ms | time s (min-max) | vs os-default | vs lru |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| os-default | 408 | 60 | 17062 | - | - | 0.0 | 750.0 | 4% | 0.0 | 0.0 | 8.87 (8.84-9.87) | 1.00x | 1.04x |
| os-noreadahead | 779 | 804 | 1203 | - | - | 0.0 | 750.0 | 6% | 0.0 | 0.0 | 11.23 (11.03-11.42) | 0.79x | 0.82x |
| lru | 468 | 132 | 16758 | 0% | - | 0.0 | 750.0 | 4% | 0.0 | 0.0 | 9.19 (8.72-9.47) | 0.97x | 1.00x |
| sequential | 462 | 9 | 18086 | 100% | 100% | 0.0 | 750.0 | 6% | 38.2 | 27.4 | 9.42 (8.83-9.84) | 0.94x | 0.98x |
| markov2 | 507 | 103 | 15717 | 0% | - | 0.0 | 750.0 | 5% | 0.4 | 39.7 | 9.55 (8.88-10.05) | 0.93x | 0.96x |
| markov2+gate | 556 | 113 | 17250 | 0% | - | 0.0 | 750.0 | 5% | 0.0 | 42.1 | 9.81 (8.48-9.88) | 0.90x | 0.94x |
| oracle | 502 | 9 | 23204 | 100% | 100% | 0.0 | 750.0 | 7% | 38.2 | 29.1 | 9.75 (9.37-9.76) | 0.91x | 0.94x |

## random

| config | mean us | p95 us | p99 us | hit | accuracy | wasted MiB | device MiB | cpu | RSS+ MiB | predictor ms | time s (min-max) | vs os-default | vs lru |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| os-default | 10024 | 15239 | 34920 | - | - | 0.0 | 728.5 | 1% | 0.0 | 0.0 | 66.72 (63.65-69.37) | 1.00x | 1.00x |
| os-noreadahead | 9860 | 15197 | 34542 | - | - | 0.0 | 724.2 | 2% | 0.0 | 0.0 | 65.75 (65.05-67.04) | 1.01x | 1.01x |
| lru | 10040 | 15423 | 36594 | 3% | - | 0.0 | 728.5 | 1% | 0.0 | 0.0 | 66.63 (63.29-68.54) | 1.00x | 1.00x |
| sequential | 9527 | 14940 | 27317 | 3% | 0% | 1.5 | 734.5 | 1% | 0.1 | 7.0 | 63.58 (63.45-65.74) | 1.05x | 1.05x |
| markov2 | 9798 | 15110 | 30775 | 3% | - | 0.0 | 728.5 | 2% | 0.0 | 52.5 | 65.24 (63.68-68.35) | 1.02x | 1.02x |
| markov2+gate | 9694 | 14975 | 30042 | 3% | - | 0.0 | 728.5 | 1% | 0.0 | 50.8 | 64.62 (63.59-67.17) | 1.03x | 1.03x |
| oracle | 7309 | 31594 | 42894 | 100% | 100% | 0.0 | 727.7 | 2% | 26.2 | 33.6 | 50.52 (48.87-52.42) | 1.32x | 1.32x |


# Robust analysis (paired by repeat; `*` = disturbed run, excluded)

## recurring_routines

Paired against `lru`, repeat by repeat. `speedup` = baseline time / config time over repeats where both ran undisturbed.

| config | times (s) | disturbed runs | median of clean runs (s) | speedup vs lru | faster in |
| --- | --- | ---: | ---: | ---: | ---: |
| sequential | 63.4, 61.0, 199.4* | 1 | 62.20 | 0.97x | 0 of 2 |
| oracle | 46.3, 46.4, 122.2* | 1 | 46.33 | 1.30x | 2 of 2 |
| markov2+gate | 62.9, 61.5, 61.6 | 0 | 61.60 | 0.97x | 0 of 3 |
| lru | 61.1, 59.8, 59.5 | 0 | 59.76 | - | - |
| os-default | 63.6, 59.4, 195.7* | 1 | 61.54 | 0.98x | 1 of 2 |
| markov2 | 65.0, 62.8, 63.2 | 0 | 63.22 | 0.94x | 0 of 3 |
| os-noreadahead | 62.8, 64.8, 63.7 | 0 | 63.73 | 0.93x | 0 of 3 |

## dl_fixed_order

Paired against `lru`, repeat by repeat. `speedup` = baseline time / config time over repeats where both ran undisturbed.

| config | times (s) | disturbed runs | median of clean runs (s) | speedup vs lru | faster in |
| --- | --- | ---: | ---: | ---: | ---: |
| sequential | 163.2*, 52.2, 53.5 | 1 | 52.88 | 1.01x | 1 of 2 |
| oracle | 81.1*, 43.7, 44.4 | 1 | 44.03 | 1.21x | 2 of 2 |
| markov2+gate | 156.0*, 51.6, 51.8 | 1 | 51.73 | 1.03x | 2 of 2 |
| lru | 93.4*, 53.0, 53.4 | 1 | 53.20 | - | - |
| os-default | 54.8, 52.6, 55.1 | 0 | 54.83 | 0.99x | 1 of 2 |
| markov2 | 52.1, 51.9, 52.6 | 0 | 52.06 | 1.02x | 2 of 2 |
| os-noreadahead | 64.6, 65.7, 66.0 | 0 | 65.65 | 0.81x | 0 of 2 |

## dl_reshuffled

Paired against `lru`, repeat by repeat. `speedup` = baseline time / config time over repeats where both ran undisturbed.

| config | times (s) | disturbed runs | median of clean runs (s) | speedup vs lru | faster in |
| --- | --- | ---: | ---: | ---: | ---: |
| sequential | 51.7, 54.6, 54.0 | 0 | 53.95 | 1.00x | 1 of 3 |
| oracle | 43.9, 46.1, 44.6 | 0 | 44.57 | 1.21x | 3 of 3 |
| markov2+gate | 52.3, 55.6, 52.9 | 0 | 52.94 | 1.02x | 2 of 3 |
| lru | 53.2, 52.1, 53.8 | 0 | 53.22 | - | - |
| os-default | 51.8, 53.1, 54.3 | 0 | 53.11 | 0.99x | 1 of 3 |
| markov2 | 52.3, 56.4, 53.8 | 0 | 53.82 | 1.00x | 1 of 3 |
| os-noreadahead | 63.0, 63.2, 66.4 | 0 | 63.24 | 0.82x | 0 of 3 |

## sequential

Paired against `lru`, repeat by repeat. `speedup` = baseline time / config time over repeats where both ran undisturbed.

| config | times (s) | disturbed runs | median of clean runs (s) | speedup vs lru | faster in |
| --- | --- | ---: | ---: | ---: | ---: |
| sequential | 8.8, 9.8, 9.4 | 0 | 9.42 | 0.98x | 1 of 3 |
| oracle | 9.4, 9.8, 9.8 | 0 | 9.75 | 0.94x | 1 of 3 |
| markov2+gate | 9.8, 8.5, 9.9 | 0 | 9.81 | 0.97x | 1 of 3 |
| lru | 9.5, 8.7, 9.2 | 0 | 9.19 | - | - |
| os-default | 8.8, 8.9, 9.9 | 0 | 8.87 | 0.98x | 1 of 3 |
| markov2 | 9.6, 10.1, 8.9 | 0 | 9.55 | 0.99x | 1 of 3 |
| os-noreadahead | 11.2, 11.4, 11.0 | 0 | 11.23 | 0.83x | 0 of 3 |

## random

Paired against `lru`, repeat by repeat. `speedup` = baseline time / config time over repeats where both ran undisturbed.

| config | times (s) | disturbed runs | median of clean runs (s) | speedup vs lru | faster in |
| --- | --- | ---: | ---: | ---: | ---: |
| sequential | 65.7, 63.5, 63.6 | 0 | 63.58 | 1.01x | 2 of 3 |
| oracle | 50.5, 52.4, 48.9 | 0 | 50.52 | 1.31x | 3 of 3 |
| markov2+gate | 67.2, 63.6, 64.6 | 0 | 64.62 | 0.99x | 1 of 3 |
| lru | 66.6, 68.5, 63.3 | 0 | 66.63 | - | - |
| os-default | 66.7, 69.4, 63.6 | 0 | 66.72 | 0.99x | 0 of 3 |
| markov2 | 68.3, 65.2, 63.7 | 0 | 65.24 | 0.99x | 1 of 3 |
| os-noreadahead | 67.0, 65.0, 65.8 | 0 | 65.75 | 0.99x | 1 of 3 |

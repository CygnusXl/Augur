# Break-even bandwidth of augur-cm versus sending raw (Mbit/s)

Coding is faster than raw below this bandwidth. Derived from measured ratio and throughput.

| file | static | sequential | pipelined |
| --- | ---: | ---: | ---: |
| dna_bacterial | 3.08 | 1.54 | 4.14 |
| executable_elf | 2.73 | 1.37 | 3.98 |
| json_metadata | 5.25 | 2.66 | 5.71 |
| prose_docs | 3.27 | 1.64 | 3.92 |
| source_code | 3.61 | 1.76 | 4.20 |
| system_log | 5.88 | 2.96 | 6.13 |

# Fastest option by link speed (static scenario, 1 MiB file)

| file | 0.5 Mbit/s | 2 Mbit/s | 10 Mbit/s | 50 Mbit/s | 250 Mbit/s |
| --- | --- | --- | --- | --- | --- |
| dna_bacterial | brotli-11 | brotli-11 | zstd-19 | zstd-19 | zstd-19 |
| executable_elf | xz-9e | xz-9e | brotli-11 | zstd-19 | zstd-19 |
| json_metadata | brotli-11 | brotli-11 | brotli-11 | zstd-19 | zstd-19 |
| prose_docs | brotli-11 | brotli-11 | brotli-11 | zstd-19 | zstd-19 |
| source_code | brotli-11 | brotli-11 | brotli-11 | zstd-19 | zstd-19 |
| system_log | bzip2-9 | xz-9e | brotli-11 | zstd-19 | zstd-19 |

# Where does augur-cm win on time? (static scenario)

| file | fastest below (Mbit/s) | speed-up needed at 2 | at 10 | at 50 |
| --- | ---: | ---: | ---: | ---: |
| dna_bacterial | 0.079 | 22x | 106x | 442x |
| executable_elf | never | inf | inf | 822x |
| json_metadata | 0.035 | 53x | 214x | 570x |
| prose_docs | 0.081 | 23x | 105x | 348x |
| source_code | 0.093 | 21x | 93x | 329x |
| system_log | 0.11 | 16x | 72x | 321x |

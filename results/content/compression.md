# Compression results (measured)

Machine: Linux-6.18.44-fc-v153-x86_64-with-glibc2.39, x86_64, Python 3.13.17. Median of 3 runs, single thread. Every output was decompressed and checked byte-for-byte against the input.

## Bits per byte (lower is better; 8.00 = no compression)

| file | bytes | gzip-9 | bzip2-9 | xz-9e | zstd-19 | brotli-11 | augur-cm |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| dna_bacterial | 1048576 | 2.358 | 2.272 | 2.207 | 2.217 | 2.198 | **2.044** |
| dna_viral | 30322 | 2.526 | 2.321 | 2.382 | 2.261 | 2.214 | **2.063** |
| executable_elf | 1023032 | 2.876 | 2.861 | **2.389** | 2.555 | 2.446 | 2.512 |
| json_metadata | 1048576 | 0.895 | 0.691 | 0.711 | 0.739 | 0.692 | **0.643** |
| precompressed_gzip | 1048576 | 8.003 | 8.041 | 8.001 | 8.000 | 8.000 | **8.000** |
| precompressed_jpeg | 292349 | 7.465 | 7.363 | 7.358 | 7.364 | 7.279 | **7.238** |
| prose_docs | 563555 | 2.258 | 1.604 | 1.544 | 1.572 | 1.493 | **1.325** |
| random_control | 1048576 | 8.003 | 8.039 | 8.001 | 8.000 | 8.000 | **8.000** |
| source_code | 1048576 | 1.934 | 1.636 | 1.627 | 1.656 | 1.602 | **1.432** |
| system_log | 683440 | 0.671 | 0.459 | 0.464 | 0.492 | 0.486 | **0.315** |

## Compress throughput (MB/s of input)

| file | gzip-9 | bzip2-9 | xz-9e | zstd-19 | brotli-11 | augur-cm |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| dna_bacterial | 1.26 | 10.62 | 1.59 | 1.88 | 0.35 | 0.52 |
| dna_viral | 2.53 | 11.28 | 0.64 | 2.28 | 0.43 | 0.24 |
| executable_elf | 6.26 | 15.19 | 2.46 | 3.92 | 0.44 | 0.50 |
| json_metadata | 33.30 | 11.72 | 1.91 | 2.15 | 0.58 | 0.73 |
| precompressed_gzip | 40.64 | 8.81 | 3.42 | 17.94 | 1.55 | 0.39 |
| precompressed_jpeg | 32.03 | 9.91 | 2.54 | 9.03 | 0.31 | 0.39 |
| prose_docs | 12.83 | 13.24 | 2.38 | 4.17 | 0.65 | 0.49 |
| random_control | 42.19 | 8.78 | 3.38 | 14.36 | 2.59 | 0.39 |
| source_code | 6.82 | 13.59 | 2.32 | 2.87 | 0.50 | 0.52 |
| system_log | 25.29 | 11.28 | 2.43 | 2.49 | 0.54 | 0.78 |

## Decompress throughput (MB/s of output)

| file | gzip-9 | bzip2-9 | xz-9e | zstd-19 | brotli-11 | augur-cm |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| dna_bacterial | 247.76 | 18.36 | 68.54 | 1105.34 | 106.02 | 0.52 |
| dna_viral | 256.65 | 29.07 | 52.61 | 89.19 | 100.44 | 0.24 |
| executable_elf | 198.41 | 28.98 | 46.36 | 631.47 | 186.29 | 0.50 |
| json_metadata | 504.78 | 54.26 | 89.77 | 1908.53 | 624.92 | 0.71 |
| precompressed_gzip | 2067.65 | 15.04 | 1330.49 | 7667.94 | 4197.39 | 10550.54 |
| precompressed_jpeg | 172.00 | 17.14 | 14.51 | 1039.26 | 98.19 | 0.36 |
| prose_docs | 233.36 | 32.25 | 82.56 | 1089.71 | 394.76 | 0.49 |
| random_control | 2175.33 | 15.24 | 1194.95 | 7681.20 | 3774.04 | 9333.54 |
| source_code | 283.66 | 31.35 | 74.40 | 945.17 | 386.41 | 0.55 |
| system_log | 589.20 | 69.63 | 205.54 | 1951.65 | 972.93 | 0.77 |

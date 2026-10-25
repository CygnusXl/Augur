# Baseline check (measured)

## 1. Python bindings versus command-line tools (compressed bytes)

| file | gzip lib | gzip CLI | bzip2 lib | bzip2 CLI | xz lib | xz CLI |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| dna_bacterial | 309046 | 308961 | 297854 | 297854 | 289340 | 289340 |
| dna_viral | 9576 | 9576 | 8798 | 8798 | 9028 | 9028 |
| executable_elf | 367718 | 366917 | 365915 | 365915 | 305456 | 305456 |
| json_metadata | 117270 | 117231 | 90538 | 90538 | 93256 | 93256 |
| precompressed_gzip | 1048914 | 1048754 | 1053906 | 1053906 | 1048688 | 1048688 |
| precompressed_jpeg | 272804 | 272499 | 269057 | 269057 | 268896 | 268896 |
| prose_docs | 159040 | 158875 | 112998 | 112998 | 108756 | 108756 |
| random_control | 1048914 | 1048754 | 1053623 | 1053623 | 1048688 | 1048688 |
| source_code | 253530 | 253564 | 214392 | 214392 | 213296 | 213296 |
| system_log | 57359 | 57410 | 39201 | 39201 | 39616 | 39616 |

Largest size difference between a Python binding and its CLI: 801 bytes.

## 2. Stronger baseline settings (bits per byte)

| file | zstd-19 | zstd-22 long | brotli-11 generic | brotli-11 text | best baseline | augur-cm |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| dna_bacterial | 2.217 | 2.217 | 2.198 | 2.198 | 2.198 | 2.044 |
| dna_viral | 2.261 | 2.261 | 2.214 | 2.214 | 2.214 | 2.063 |
| executable_elf | 2.555 | 2.555 | 2.446 | 2.446 | 2.389 | 2.512 |
| json_metadata | 0.739 | 0.737 | 0.692 | 0.692 | 0.691 | 0.643 |
| precompressed_gzip | 8.000 | 8.000 | 8.000 | 8.000 | 8.000 | 8.000 |
| precompressed_jpeg | 7.364 | 7.364 | 7.279 | 7.279 | 7.279 | 7.238 |
| prose_docs | 1.572 | 1.571 | 1.493 | 1.493 | 1.493 | 1.325 |
| random_control | 8.000 | 8.000 | 8.000 | 8.000 | 8.000 | 8.000 |
| source_code | 1.656 | 1.656 | 1.602 | 1.602 | 1.602 | 1.432 |
| system_log | 0.492 | 0.492 | 0.486 | 0.486 | 0.459 | 0.315 |

## 3. Order-0 empirical entropy (bits per byte)

| file | order-0 entropy | best baseline | augur-cm |
| --- | ---: | ---: | ---: |
| dna_bacterial | 2.057 | 2.198 | 2.044 |
| dna_viral | 2.075 | 2.214 | 2.063 |
| executable_elf | 5.697 | 2.389 | 2.512 |
| json_metadata | 4.393 | 0.691 | 0.643 |
| precompressed_gzip | 7.998 | 8.000 | 8.000 |
| precompressed_jpeg | 7.874 | 7.279 | 7.238 |
| prose_docs | 4.706 | 1.493 | 1.325 |
| random_control | 8.000 | 8.000 | 8.000 |
| source_code | 4.563 | 1.602 | 1.432 |
| system_log | 4.883 | 0.459 | 0.315 |

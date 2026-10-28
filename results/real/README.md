# Real-I/O results: which run is which

All runs: Peter's workstation (Ubuntu, 61 GiB RAM, rotational drive, ext4), 6000 accesses per workload,
application cache = 5% of unique bytes, think time 1 ms, prefetch depth 4, 4 prefetch threads, file evicted
from the page cache before every run. Access orders are synthetic.

| folder | design | repeats | status |
| --- | --- | ---: | --- |
| `peter-pc/` | immediate page-cache drop in application configurations | 1 | superseded; first look |
| `peter-pc-3rep/` | immediate drop | 3 | valid for comparisons *among* application configurations; **unfair to them versus `os-default`** |
| `diagnostic-lazy-drop/` | both designs side by side (`-lazy` = new design) | 2 | shows why: dropping right after the read cost the application configurations 17-24% on image-sized items |
| `final-default-design/` | default design: kernel keeps an item until the application cache evicts it | 3 | **use for conclusions**; read `analysis.md` (paired by repeat, disturbed runs flagged) rather than the median table, because several runs were stalled by something else using the drive |
| `peter-pc-3rep-local/`, `peter-pc-lazy/`, `peter-pc/` | raw files pushed from the workstation (`runs.csv`) | | same data as the folders above |

Absolute times vary between runs (the same configuration took 63 s in one run and 85 s in another on
`dl_fixed_order`, probably file placement on the disk or background activity). Compare configurations only
within a single run.

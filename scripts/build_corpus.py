#!/usr/bin/env python3
"""Assemble the real-data corpus used by the content benchmark.

    python scripts/build_corpus.py --out data

Writes ``data/test`` (reported results) and ``data/tune`` (a separate set used
only to pick codec parameters), plus ``MANIFEST.json`` with a SHA-256 for every
file. Files come from this machine (Python standard library, system logs, a
compiled binary, JSON metadata, a JPEG) and from public GitHub test data (DNA).
Types whose source is missing are skipped with a warning, so numbers from
another machine are comparable only through the manifest hashes. The corpus
is not committed to the repository.
"""

from __future__ import annotations

import argparse
import glob
import gzip
import hashlib
import json
import os
import random
import shutil
import sysconfig
import urllib.request

MiB = 1024 * 1024
NF = "https://raw.githubusercontent.com/nf-core/test-datasets/modules/data/genomics/"
BIO = "https://raw.githubusercontent.com/biopython/biopython/master/Tests/GenBank/"


def read(path: str, limit: int | None = None, offset: int = 0) -> bytes:
    with open(path, "rb") as fh:
        fh.seek(offset)
        return fh.read(limit) if limit else fh.read()


def concat(paths, limit: int) -> bytes:
    out = bytearray()
    for p in paths:
        if len(out) >= limit:
            break
        try:
            out += read(p)
        except OSError:
            pass
    return bytes(out[:limit])


def fetch(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=60) as r:
        return r.read()


def build(out: str) -> dict:
    std = sysconfig.get_paths()["stdlib"]
    py = sorted(glob.glob(os.path.join(std, "*.py")))
    json_files = sorted(
        p for p in glob.glob(os.path.expanduser("~/.cache/uv/archive-v0/*/**/*.json"), recursive=True)
        if os.path.getsize(p) > 200
    )
    items = {"test": {}, "tune": {}}  # name -> (bytes, provenance)

    def add(split, name, fn, prov):
        try:
            data = fn()
        except Exception as exc:  # missing source on this machine
            print(f"skip {split}/{name}: {exc}")
            return
        if data:
            items[split][name] = (data, prov)

    add("test", "source_code", lambda: concat(py[0::2], MiB), "Python stdlib *.py, even-indexed files, first 1 MiB")
    add("tune", "source_code", lambda: concat(py[1::2], MiB // 2), "Python stdlib *.py, odd-indexed files, first 512 KiB")
    add("test", "prose_docs", lambda: read(os.path.join(std, "pydoc_data", "topics.py"), MiB), "pydoc_data/topics.py (Python language reference text)")
    add("tune", "prose_docs", lambda: concat(sorted(glob.glob("/usr/share/common-licenses/*")), MiB // 2), "/usr/share/common-licenses/*")
    add("test", "system_log", lambda: read("/var/log/dpkg.log", MiB), "/var/log/dpkg.log")
    add("tune", "system_log", lambda: read("/var/log/apt/term.log", MiB // 2), "/var/log/apt/term.log")
    add("test", "json_metadata", lambda: concat(json_files[0::2], MiB), "JSON files from the uv cache, even-indexed, first 1 MiB")
    add("tune", "json_metadata", lambda: concat(json_files[1::2], MiB // 2), "JSON files from the uv cache, odd-indexed, first 512 KiB")
    gcc = shutil.which("gcc")
    add("test", "executable_elf", lambda: read(os.path.realpath(gcc), MiB), "gcc driver binary, first 1 MiB")
    add("tune", "executable_elf", lambda: read("/usr/bin/python3.11", MiB // 4, MiB), "python3.11 binary, 256 KiB from offset 1 MiB")
    bf = {}
    def bacterial():
        bf["gz"] = fetch(NF + "prokaryotes/bacteroides_fragilis/genome/genome.fna.gz")
        bf["fa"] = gzip.decompress(bf["gz"])
        return bf["fa"][:MiB]
    add("test", "dna_bacterial", bacterial, "Bacteroides fragilis chromosome (nf-core/test-datasets), first 1 MiB of FASTA")
    add("test", "dna_viral", lambda: fetch(NF + "sarscov2/genome/genome.fasta"), "SARS-CoV-2 genome MT192765.1 FASTA (nf-core/test-datasets)")
    add("tune", "dna_plasmid", lambda: fetch(BIO + "NC_005816.fna"), "Yersinia pestis plasmid pPCP1 FASTA (biopython tests)")
    add("test", "precompressed_gzip", lambda: bf["gz"][:MiB], "gzip file of the B. fragilis genome, first 1 MiB (already compressed)")
    jpgs = sorted(glob.glob("/usr/share/texlive/**/*.jpg", recursive=True), key=os.path.getsize, reverse=True)
    add("test", "precompressed_jpeg", lambda: read(jpgs[0], MiB), f"JPEG image {os.path.basename(jpgs[0])} (already compressed)")
    add("test", "random_control", lambda: random.Random(0).randbytes(MiB), "random.Random(0).randbytes(1 MiB) (incompressible control)")

    manifest = {}
    for split, files in items.items():
        d = os.path.join(out, split)
        os.makedirs(d, exist_ok=True)
        for name, (data, prov) in files.items():
            with open(os.path.join(d, name + ".bin"), "wb") as fh:
                fh.write(data)
            manifest[f"{split}/{name}"] = {
                "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(), "source": prov}
    with open(os.path.join(out, "MANIFEST.json"), "w") as fh:
        json.dump(manifest, fh, indent=2)
    return manifest


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="data")
    args = ap.parse_args()
    for k, v in build(args.out).items():
        print(f"{k:28s} {v['bytes']:>9d}  {v['sha256'][:12]}  {v['source']}")

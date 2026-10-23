"""When does compressing before sending beat sending raw bytes?

A closed-form model, not a network simulation. Inputs are measured: the
compression ratio and the codec's compress and decompress throughput (bytes of
*original* data per second). Three scenarios:

* ``static``     the sender compressed the file ahead of time, so only the
                 transfer and the receiver's decompression are on the clock;
* ``sequential`` compress, then send, then decompress, one after the other;
* ``pipelined``  chunked streaming where the three stages overlap perfectly
                 (an optimistic idealisation: time is set by the slowest stage).

Raw transfer time is ``rtt + size / bandwidth``. Every function takes
bandwidth in bytes per second.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Optional

SCENARIOS = ("static", "sequential", "pipelined")


@dataclass(frozen=True)
class CodecProfile:
    name: str
    ratio: float  # compressed / original
    compress_Bps: float  # original bytes per second
    decompress_Bps: float


def raw_time(size: float, bandwidth: float, rtt: float = 0.0) -> float:
    return rtt + size / bandwidth


def coded_time(size: float, c: CodecProfile, bandwidth: float, scenario: str = "static", rtt: float = 0.0) -> float:
    t_wire = c.ratio * size / bandwidth
    t_enc = size / c.compress_Bps
    t_dec = size / c.decompress_Bps
    if scenario == "static":
        return rtt + t_wire + t_dec
    if scenario == "sequential":
        return rtt + t_enc + t_wire + t_dec
    if scenario == "pipelined":
        return rtt + max(t_enc, t_wire, t_dec)
    raise ValueError(f"unknown scenario {scenario!r}")


def break_even_bandwidth(c: CodecProfile, scenario: str = "static") -> float:
    """Bandwidth (bytes/s) below which coding is faster than sending raw.

    Independent of file size and round-trip time (both cancel). Zero if the
    codec does not shrink the data.
    """
    r = c.ratio
    if r >= 1.0:
        return 0.0
    if scenario == "static":
        return (1.0 - r) * c.decompress_Bps
    if scenario == "sequential":
        return (1.0 - r) / (1.0 / c.compress_Bps + 1.0 / c.decompress_Bps)
    if scenario == "pipelined":
        return min(c.compress_Bps, c.decompress_Bps)
    raise ValueError(f"unknown scenario {scenario!r}")


def fastest(size: float, codecs: Iterable[CodecProfile], bandwidth: float, scenario: str = "static",
            rtt: float = 0.0) -> str:
    """Name of the quickest option at this bandwidth, ``"raw"`` if sending uncompressed wins."""
    best_name: Optional[str] = "raw"
    best = raw_time(size, bandwidth, rtt)
    for c in codecs:
        t = coded_time(size, c, bandwidth, scenario, rtt)
        if t < best:
            best, best_name = t, c.name
    return best_name or "raw"


def mbit_to_Bps(mbit_per_s: float) -> float:
    return mbit_per_s * 1e6 / 8.0


def Bps_to_mbit(bytes_per_s: float) -> float:
    return bytes_per_s * 8.0 / 1e6


def profiles_from_rows(rows: Iterable[Dict], file: str) -> list:
    return [
        CodecProfile(r["codec"], float(r["ratio"]), float(r["compress_MBps"]) * 1e6, float(r["decompress_MBps"]) * 1e6)
        for r in rows
        if r["file"] == file
    ]

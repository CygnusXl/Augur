"""Python binding for the exact predictive codec (``augur_cm.c``).

The C source is compiled on first use with the system C compiler and cached.
Compression is lossless: ``decompress(compress(x)) == x`` for every byte string.
"""

from __future__ import annotations

import ctypes
import hashlib
import os
import subprocess
import tempfile
from functools import lru_cache
from typing import Dict, Optional

_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "augur_cm.c")


def _cache_dir() -> str:
    base = os.environ.get("AUGUR_CACHE") or os.path.join(tempfile.gettempdir(), "augur-build")
    os.makedirs(base, exist_ok=True)
    return base


@lru_cache(maxsize=None)
def _library(defs_key: tuple) -> ctypes.CDLL:
    with open(_SRC, "rb") as fh:
        digest = hashlib.sha256(fh.read() + repr(defs_key).encode()).hexdigest()[:16]
    so = os.path.join(_cache_dir(), f"augur_cm_{digest}.so")
    if not os.path.exists(so):
        cmd = ["cc", "-O2", "-shared", "-fPIC", "-std=c99", "-o", so + ".tmp", _SRC]
        cmd[1:1] = [f"-D{k}={v}" for k, v in defs_key]
        subprocess.run(cmd, check=True, capture_output=True)
        os.replace(so + ".tmp", so)
    lib = ctypes.CDLL(so)
    lib.augur_cm_bound.restype = ctypes.c_size_t
    lib.augur_cm_bound.argtypes = [ctypes.c_size_t]
    lib.augur_cm_compress.restype = ctypes.c_size_t
    lib.augur_cm_compress.argtypes = [ctypes.c_char_p, ctypes.c_size_t, ctypes.c_char_p, ctypes.c_size_t]
    lib.augur_cm_decompress.restype = ctypes.c_size_t
    lib.augur_cm_decompress.argtypes = [ctypes.c_char_p, ctypes.c_size_t, ctypes.c_char_p, ctypes.c_size_t]
    return lib


class AugurCM:
    """Context-mixing codec. ``params`` override compile-time constants
    (``AUGUR_TABLE_BITS``, ``AUGUR_MIX_LR``, ``AUGUR_LIMIT``) for ablations."""

    name = "augur-cm"

    def __init__(self, **params: int):
        self.params: Dict[str, int] = dict(params)
        self._lib = _library(tuple(sorted(self.params.items())))

    # Container: 1 mode byte, then either the raw input (STORED) or the CM stream (MODELLED).
    # Incompressible input (random, encrypted, already compressed) makes the model learn noise and
    # expand slightly, so the encoder falls back to storing the data after a 1-byte flag.
    STORED, MODELLED = 0, 1

    def compress_raw(self, data: bytes) -> bytes:
        """The bare context-mixing stream, with no stored-mode fallback."""
        cap = int(self._lib.augur_cm_bound(len(data)))
        out = ctypes.create_string_buffer(cap)
        n = self._lib.augur_cm_compress(data, len(data), out, cap)
        if n == 0:
            raise RuntimeError("augur-cm: compression failed")
        return out.raw[:n]

    def compress(self, data: bytes) -> bytes:
        body = self.compress_raw(data)
        if len(body) >= len(data):
            return bytes([self.STORED]) + data
        return bytes([self.MODELLED]) + body

    def decompress(self, blob: bytes) -> bytes:
        if len(blob) < 1:
            raise ValueError("augur-cm: stream too short")
        mode, body = blob[0], blob[1:]
        if mode == self.STORED:
            return body
        if mode != self.MODELLED:
            raise ValueError("augur-cm: unknown container mode")
        if len(body) < 8:
            raise ValueError("augur-cm: stream too short")
        n = int.from_bytes(body[:8], "little")
        if n == 0:
            return b""
        out = ctypes.create_string_buffer(n)
        got = self._lib.augur_cm_decompress(body, len(body), out, n)
        if got != n:
            raise ValueError("augur-cm: corrupt stream")
        return out.raw[:n]


def compress(data: bytes) -> bytes:
    return AugurCM().compress(data)


def decompress(blob: bytes) -> bytes:
    return AugurCM().decompress(blob)

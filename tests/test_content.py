import os
import random

import pytest

from augur.content.codec import AugurCM

rng = random.Random(7)
codec = AugurCM(AUGUR_TABLE_BITS=16)  # small tables keep the suite fast; same code path


def roundtrip(data: bytes) -> bytes:
    blob = codec.compress(data)
    assert codec.decompress(blob) == data
    return blob


def test_empty_and_single_byte():
    assert codec.decompress(codec.compress(b"")) == b""
    for b in (0, 1, 127, 128, 255):
        roundtrip(bytes([b]))


def test_all_byte_values_and_short_inputs():
    roundtrip(bytes(range(256)))
    for n in range(1, 40):
        roundtrip(rng.randbytes(n))


def test_random_bytes_are_exact_and_barely_expand():
    data = rng.randbytes(50_000)
    blob = roundtrip(data)
    assert len(blob) == len(data) + 1  # stored-mode fallback: one flag byte of overhead
    assert len(codec.compress_raw(data)) > len(data)  # the bare model does expand random data


def test_repetitive_data_shrinks_a_lot():
    data = b"GET /index.html 200\n" * 5000
    blob = roundtrip(data)
    assert len(blob) < len(data) / 50


def test_text_beats_stored_size():
    text = open(__file__, "rb").read() * 3
    blob = roundtrip(text)
    assert len(blob) < len(text) / 3


def test_long_runs_and_boundary_patterns():
    roundtrip(b"\x00" * 100_000)
    roundtrip(b"\xff" * 100_000)
    roundtrip((b"\x00\xff" * 30_000))


def test_fuzz_many_sizes_and_alphabets():
    for _ in range(40):
        n = rng.randint(0, 3000)
        alphabet = rng.choice([2, 4, 16, 256])
        roundtrip(bytes(rng.randrange(alphabet) for _ in range(n)))


def test_deterministic_output():
    data = rng.randbytes(2000) + b"abc" * 500
    assert codec.compress(data) == codec.compress(data)
    assert AugurCM(AUGUR_TABLE_BITS=16).compress(data) == codec.compress(data)


def test_corrupt_or_truncated_streams_never_crash():
    data = open(__file__, "rb").read()
    blob = bytearray(codec.compress(data))
    for _ in range(25):
        bad = bytearray(blob)
        bad[rng.randrange(9, len(bad))] ^= 1 << rng.randrange(8)
        try:
            out = codec.decompress(bytes(bad))
            assert len(out) == len(data)  # stored length is intact; content may differ
        except ValueError:
            pass
    for cut in (0, 1, 3, 9, 13, len(blob) // 2):
        try:
            codec.decompress(bytes(blob[:cut]))
        except ValueError:
            pass


def test_declared_length_too_large_is_rejected_not_allocated_blindly():
    # 8-byte header claiming 2**40 bytes of output with a tiny body
    blob = bytes([1]) + (2**40).to_bytes(8, "little") + b"\x00" * 8
    with pytest.raises((ValueError, MemoryError, RuntimeError)):
        codec.decompress(blob)

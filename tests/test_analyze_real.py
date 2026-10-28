import importlib.util
import os

spec = importlib.util.spec_from_file_location(
    "analyze_real", os.path.join(os.path.dirname(__file__), "..", "scripts", "analyze_real.py"))
ar = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ar)

LOG = """[w1] writing 1 MiB ...
  rep 0 lru                10.00 s   p99 1 us   device read 1.0 MiB
  rep 1 lru                10.40 s   p99 1 us   device read 1.0 MiB
  rep 2 lru                30.00 s   p99 1 us   device read 1.0 MiB
  rep 0 fast                5.00 s   p99 1 us   device read 1.0 MiB
  rep 1 fast                5.20 s   p99 1 us   device read 1.0 MiB
  rep 2 fast                5.10 s   p99 1 us   device read 1.0 MiB
"""


def test_log_parse_flags_disturbed_and_pairs(tmp_path):
    p = tmp_path / "log.txt"
    p.write_text(LOG)
    data = ar.load(str(p))
    assert data[("w1", "lru")] == {0: 10.0, 1: 10.4, 2: 30.0}
    text = ar.analyse(data, "lru")
    assert "30.0*" in text                       # the stalled run is flagged
    assert "2.00x" in text or "1.98x" in text or "2.0" in text
    assert "2 of 2" in text                      # disturbed repeat excluded from the pairing

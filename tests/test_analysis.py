import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from holder_report import analysis as A  # noqa: E402
from holder_report.config import WEI  # noqa: E402
from holder_report.flows import reconcile  # noqa: E402


def w(x):
    return int(x * WEI)


def test_band_edges():
    assert A.band_of(w(100_000_000)) == "10 million or more"
    assert A.band_of(w(9_999_999.9)) == "1 million to 10 million"
    assert A.band_of(w(1)) == "1 to 100"
    assert A.band_of(w(0.5)) == "Less than 1"


def test_positions_add_wrapped_and_staked_and_skip_named():
    native = {"a": w(10), "b": w(5), "named": w(1000)}
    wrbnt = {"a": w(2), "c": w(7)}
    staked = {"pool1": {"a": w(1), "b": w(3)}, "pool2": {"c": w(4)}}
    pos = A.positions(native, wrbnt, staked, exclude={"named"})
    assert pos == {"a": w(13), "b": w(8), "c": w(11)}


def test_distribution_counts_and_totals():
    pos = {"a": w(150_000_000), "b": w(50), "c": w(60), "d": w(0.2)}
    d = A.distribution(pos)
    assert d["10 million or more"] == (1, w(150_000_000))
    assert d["1 to 100"] == (2, w(110))
    assert d["Less than 1"] == (1, w(0.2))
    assert sum(c for c, _ in d.values()) == 4


def test_gini_extremes():
    assert A.gini([5, 5, 5, 5]) == 0.0
    g = A.gini([0, 0, 0, 100])
    assert g == 0.0  # zeros are not holders; one holder alone is equal to itself
    assert abs(A.gini([1, 1, 1, 97]) - 0.72) < 1e-9


def test_top_share_and_holders_for_share():
    vals = [50, 30, 10, 5, 5]
    assert A.top_share(vals, 1) == 0.5
    assert A.top_share(vals, 2) == 0.8
    assert A.holders_for_share(vals, 0.5) == 1
    assert A.holders_for_share(vals, 0.81) == 3


def test_classify_change_threshold():
    assert A.classify_change(w(100), w(101)) == "unchanged"
    assert A.classify_change(w(100), w(101.01)) == "added"
    assert A.classify_change(w(100), w(98)) == "reduced"
    assert A.classify_change(w(100), w(0.5)) == "exited"


def test_cohort_table_follows_same_wallets():
    start = {"big": w(20_000_000), "mid": w(200_000), "tiny": w(0.5)}
    end = {"big": w(10_000_000), "mid": w(200_000), "new": w(5_000)}
    rows = {r["cohort"]: r for r in A.cohort_table(start, end)}
    big = rows["Largest wallets (10 million or more)"]
    assert big["wallets"] == 1 and big["reduced"] == 1 and big["end_wei"] == w(10_000_000)
    mid = rows["Mid-size wallets (100,000 to 1 million)"]
    assert mid["unchanged"] == 1
    assert sum(r["wallets"] for r in rows.values()) == 2  # tiny and new are outside cohorts


def test_reconcile_zero_gap():
    moves = [("x", "y", 10, "transaction", "h1"), ("y", "z", 4, "internal", "h2")]
    res = reconcile({"y"}, {"y": 100}, {"y": 105}, moves, {"y": 1})
    assert res["y"]["gap_wei"] == 0
    assert res["y"]["in_wei"] == 10 and res["y"]["out_wei"] == 4


def test_short_format():
    assert A.fmt_rbnt_short(w(2_294_132_788)) == "2.29 billion"
    assert A.fmt_rbnt_short(w(751_300_000)) == "751.3 million"
    assert A.fmt_rbnt_short(w(15_724)) == "15,724"

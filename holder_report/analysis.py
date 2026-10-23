"""Pure functions used by the analysis step. All amounts are integers in wei
(1 RBNT = 10**18 wei) until they are written out, so sums are exact.
"""
from .config import WEI

# Holding size bands, in whole RBNT. Lower bound inclusive.
BANDS = [
    ("10 million or more", 10_000_000),
    ("1 million to 10 million", 1_000_000),
    ("100,000 to 1 million", 100_000),
    ("10,000 to 100,000", 10_000),
    ("1,000 to 10,000", 1_000),
    ("100 to 1,000", 100),
    ("1 to 100", 1),
    ("Less than 1", 0),
]

# Cohorts for the accumulation view, set by holding at the start of the quarter.
COHORTS = [
    ("Largest wallets (10 million or more)", 10_000_000),
    ("Large wallets (1 million to 10 million)", 1_000_000),
    ("Mid-size wallets (100,000 to 1 million)", 100_000),
    ("Smaller wallets (1,000 to 100,000)", 1_000),
    ("Small wallets (1 to 1,000)", 1),
]

# A wallet's holding counts as unchanged if it moved by 1% or less.
THRESHOLD_BP = 100  # basis points


def band_of(wei, bands=BANDS):
    for name, lo in bands:
        if wei >= lo * WEI:
            return name
    return None


def positions(native, wrbnt, staked, exclude):
    """Economic holding per address: native RBNT + WRBNT + RBNT staked in any pool.

    native, wrbnt: {address: wei}; staked: {pool: {address: wei}}; exclude: set of
    addresses reported by name (their holdings are reported separately).
    """
    out = {}
    for src in (native, wrbnt):
        for a, v in src.items():
            if a not in exclude and v:
                out[a] = out.get(a, 0) + v
    for pool in staked.values():
        for a, v in pool.items():
            if a not in exclude and v:
                out[a] = out.get(a, 0) + v
    return out


def distribution(pos, bands=BANDS):
    """Count and total held per band. Returns {band: (count, wei)} in band order."""
    res = {name: [0, 0] for name, _ in bands}
    for v in pos.values():
        if v <= 0:
            continue
        b = band_of(v, bands)
        res[b][0] += 1
        res[b][1] += v
    return {k: tuple(v) for k, v in res.items()}


def top_share(values, n):
    """Share (0..1) of the total held by the n largest values."""
    vals = sorted((v for v in values if v > 0), reverse=True)
    total = sum(vals)
    return (sum(vals[:n]) / total) if total else 0.0


def gini(values):
    """Gini coefficient of positive values (0 = equal, 1 = one holder has all)."""
    vals = sorted(v for v in values if v > 0)
    n = len(vals)
    if n == 0:
        return 0.0
    total = sum(vals)
    cum = 0
    for i, v in enumerate(vals, 1):
        cum += i * v
    return (2 * cum) / (n * total) - (n + 1) / n


def holders_for_share(values, share):
    """Smallest number of holders that together hold at least `share` of the total."""
    vals = sorted((v for v in values if v > 0), reverse=True)
    total = sum(vals)
    if not total:
        return 0
    acc = 0
    for i, v in enumerate(vals, 1):
        acc += v
        if acc * 1.0 >= share * total:
            return i
    return len(vals)


def classify_change(start, end, threshold_bp=THRESHOLD_BP):
    """'added', 'reduced', 'unchanged' or 'exited' (below 1 RBNT at the end)."""
    if end < WEI:
        return "exited"
    diff = end - start
    if abs(diff) * 10_000 <= threshold_bp * start:
        return "unchanged"
    return "added" if diff > 0 else "reduced"


def cohort_table(start_pos, end_pos, cohorts=COHORTS):
    """Follow the same wallets from start to end, grouped by their size at the start.

    Returns a list of dicts in cohort order. Wallets under 1 RBNT at the start
    are not in any cohort; wallets that are new over the quarter are counted
    separately by the caller.
    """
    rows = {name: {"cohort": name, "wallets": 0, "added": 0, "unchanged": 0, "reduced": 0, "exited": 0,
                   "start_wei": 0, "end_wei": 0} for name, _ in cohorts}
    for a, s in start_pos.items():
        name = band_of(s, cohorts)
        if name is None:
            continue
        e = end_pos.get(a, 0)
        r = rows[name]
        r["wallets"] += 1
        r[classify_change(s, e)] += 1
        r["start_wei"] += s
        r["end_wei"] += e
    return [rows[name] for name, _ in cohorts]


def rbnt(wei):
    """wei to RBNT as a float, for display only."""
    return wei / WEI


def fmt_int(x):
    return f"{int(round(x)):,}"


def fmt_rbnt_short(wei):
    """Plain-English short form: 2.29 billion, 751.3 million, 15,724."""
    v = wei / WEI
    a = abs(v)
    if a >= 1e9:
        return f"{v / 1e9:,.2f} billion"
    if a >= 1e6:
        return f"{v / 1e6:,.1f} million"
    return f"{v:,.0f}"


def pct(x, digits=1):
    return f"{x * 100:.{digits}f}%"

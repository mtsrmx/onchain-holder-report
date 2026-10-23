"""Step 10. Verify the published figures and the deliverables.

1. Re-read the headline figures straight from the Redbelly node (not from the
   cache) and compare them with the published CSV files.
2. Re-read a random sample of cached balances and compare.
3. Confirm the snapshot blocks sit on the right side of each boundary.
4. Scan every deliverable for anything the brief forbids: an address that is
   not publicly named, dashes the brand kit bans, emoji, prices.
5. Check every post in the X thread fits in 280 characters.

Writes data/verification.json and exits non-zero on any failure.
"""
import csv
import json
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from holder_report import config as C  # noqa: E402
from holder_report import rpc, store  # noqa: E402

WEI = C.WEI
results = []


def check(name, ok, detail=""):
    results.append({"check": name, "passed": bool(ok), "detail": str(detail)})
    print(("PASS  " if ok else "FAIL  ") + name + (f"  ({detail})" if detail and not ok else ""))


def csv_rows(name):
    with open(C.DATA / name) as f:
        return list(csv.DictReader(f))


def main():
    figs = json.loads((C.DATA / "figures.json").read_text())
    S, E = figs["start_block"], figs["end_block"]
    check("all analysis checks passed (figures.json)", figs.get("checks_passed"), "")

    # 1. Headline figures, fresh from the node.
    named = csv_rows("08_named_addresses.csv")
    for row in named:
        a = row["address"]
        for col, b in (("RBNT at start", S), ("RBNT at end", E)):
            live = int(rpc.call("eth_getBalance", [a, hex(b)]), 16)
            check(f"{row['name']} {col} matches the node", round(live / WEI) == int(row[col]), f"{live / WEI} vs {row[col]}")
    sel_total = rpc.selector("totalStake()")
    for row in csv_rows("10_staking_pools.csv"):
        for col, b in (("staked (totalStake) at start", S), ("staked at end", E)):
            live = int(rpc.call("eth_call", [{"to": row["address"], "data": sel_total}, hex(b)]), 16)
            check(f"{row['pool']} {col} matches the node", round(live / WEI) == int(row[col]), f"{live / WEI} vs {row[col]}")
    sup = rpc.selector("totalSupply()")
    for key, b in (("supply_start", S), ("supply_end", E)):
        live = int(rpc.call("eth_call", [{"to": C.WRBNT, "data": sup}, hex(b)]), 16)
        check(f"WRBNT {key} matches the node", round(live / WEI) == figs["wrbnt"][key], f"{live / WEI} vs {figs['wrbnt'][key]}")

    # 2. Random sample of cached balances.
    db = store.connect()
    rng = random.Random(151)
    for b in (S, E):
        sample = [r for r in db.execute("SELECT address, wei FROM native WHERE block=?", (b,))]
        sample = rng.sample(sample, min(300, len(sample)))
        live = rpc.run_all([("eth_getBalance", [a, hex(b)]) for a, _ in sample], workers=8)
        bad = [a for (a, w), l in zip(sample, live) if int(l, 16) != int(w)]
        check(f"300 random cached balances at block {b:,} match the node", not bad, f"{len(bad)} differ")

    # 3. Snapshot boundaries.
    for _lab, _k, ts, b, _bts in store.snapshot_blocks(db):
        t0, t1 = rpc.block_ts(b), rpc.block_ts(b + 1)
        check(f"block {b:,} is the last block before {ts}", t0 < ts <= t1, f"{t0} {t1}")

    # 4. Deliverable hygiene.
    allowed = {a.lower() for a in list(C.RESERVED) + list(C.POOL_ADDRS) + [C.WRBNT]}
    allowed |= {a.lower() for a in figs.get("labelled", {})}
    allowed.add("0x" + "0" * 40)
    addr_re = re.compile(r"0x[0-9a-fA-F]{40}(?![0-9a-fA-F])")
    banned = {chr(0x2014): "em dash", chr(0x2013): "en dash"}
    emoji_re = re.compile("[\U0001F300-\U0001FAFF\U00002600-\U000027BF]")
    price_re = re.compile(r"(\$\s?\d|\bUSD\b|price target|to the moon|buy now|should buy|should sell)", re.I)
    files = []
    for d in ("report", "community", "data"):
        files += [p for p in (C.ROOT / d).rglob("*") if p.suffix in (".html", ".md", ".csv", ".json", ".txt", ".svg")]
    files += [C.ROOT / n for n in ("README.md", "METHOD.md", "SOURCES.md") if (C.ROOT / n).exists()]
    for p in files:
        if p.name == "verification.json":
            continue
        t = p.read_text(errors="ignore")
        found = {m.group(0).lower() for m in addr_re.finditer(t)} - allowed
        check(f"{p.relative_to(C.ROOT)}: only publicly named addresses", not found, ", ".join(sorted(found))[:200])
        bad = [n for ch, n in banned.items() if ch in t]
        check(f"{p.relative_to(C.ROOT)}: no em or en dashes", not bad, bad)
        check(f"{p.relative_to(C.ROOT)}: no emoji", not emoji_re.search(t), "")
        if p.suffix != ".json":
            m = price_re.search(t)
            check(f"{p.relative_to(C.ROOT)}: no prices or trading calls", not m, m.group(0) if m else "")

    # 5. X thread.
    thread = C.ROOT / "community" / "x_thread.txt"
    if thread.exists():
        posts = [p.strip() for p in thread.read_text().split("\n---\n") if p.strip()]
        for i, p in enumerate(posts, 1):
            check(f"X post {i} is 280 characters or fewer", len(p) <= 280, f"{len(p)} characters")

    out = {"passed": all(r["passed"] for r in results), "count": len(results), "results": results}
    (C.DATA / "verification.json").write_text(json.dumps(out, indent=1))
    print(f"\n{sum(r['passed'] for r in results)}/{len(results)} checks passed")
    sys.exit(0 if out["passed"] else 1)


if __name__ == "__main__":
    main()

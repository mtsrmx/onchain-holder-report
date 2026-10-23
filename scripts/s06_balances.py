"""Step 6. Read balances from the node at the snapshot blocks.

  * native RBNT of every candidate address at the four month-end snapshots,
  * native RBNT of the named addresses at every weekly snapshot,
  * WRBNT balanceOf for every address that ever touched WRBNT, and its totalSupply,
  * the staked amount (userInfo) of every address that ever staked, and totalStake,
  * contract code at the end snapshot for every address that held anything.

Only non-zero values are stored. Resumable per snapshot.
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from holder_report import addresses as AD  # noqa: E402
from holder_report import config as C  # noqa: E402
from holder_report import rpc, store  # noqa: E402

BAL_OF = rpc.selector("balanceOf(address)")
SUPPLY = rpc.selector("totalSupply()")
USER_INFO = rpc.selector("userInfo(address)")
TOTAL_STAKE = rpc.selector("totalStake()")
UNLOCKS = rpc.selector("getStakeUnlockTimes(address)")
OWNER = rpc.selector("owner()")
W = 32


def eth_call(to, data, block):
    return ("eth_call", [{"to": to, "data": data}, hex(block)])


def progress(done, total):
    print(f"   {done:,}/{total:,} requests", flush=True)


def main():
    db = store.connect()
    store.kv_set(db, "read_on", time.strftime("%Y-%m-%d", time.gmtime()))
    snaps = store.snapshot_blocks(db)
    monthly = [(lab, b) for lab, k, _, b, _ in snaps if "month" in k]
    weekly = [(lab, b) for lab, k, _, b, _ in snaps if "week" in k or "end" in k]
    named = sorted(set(C.RESERVED) | set(C.POOL_ADDRS) | {C.WRBNT.lower()})

    cands = AD.candidates(db)
    store.kv_set(db, "candidate_count", len(cands))
    print(f"{len(cands):,} candidate addresses")

    # Native RBNT, month-end snapshots, every candidate not yet read at that block.
    # Candidates found later (for example by step 2b) are read on the next run.
    db.execute("CREATE TABLE IF NOT EXISTS read_at (block INTEGER, address TEXT, PRIMARY KEY (block, address))")
    for lab, b in monthly:
        done = {a for (a,) in db.execute("SELECT address FROM read_at WHERE block=?", (b,))}
        todo = [a for a in cands if a not in done]
        t0 = time.time()
        res = rpc.run_all([("eth_getBalance", [a, hex(b)]) for a in todo], workers=W, progress=progress)
        rows = [(a, b, str(int(r, 16))) for a, r in zip(todo, res) if int(r, 16)]
        db.executemany("INSERT OR REPLACE INTO native VALUES (?,?,?)", rows)
        db.executemany("INSERT OR IGNORE INTO read_at VALUES (?,?)", [(b, a) for a in todo])
        db.commit()
        print(f"native at {lab} block {b:,}: {len(todo):,} read, {len(rows):,} non-zero ({time.time() - t0:,.0f} s)", flush=True)

    # Native RBNT, weekly, named addresses only.
    for lab, b in weekly:
        res = rpc.run_all([("eth_getBalance", [a, hex(b)]) for a in named], workers=W)
        db.executemany("INSERT OR REPLACE INTO native VALUES (?,?,?)",
                       [(a, b, str(int(r, 16))) for a, r in zip(named, res)])
    db.commit()

    # WRBNT balances and supply.
    holders = sorted(AD.wrbnt_participants(db))
    store.kv_set(db, "wrbnt_participants", len(holders))
    for lab, b in monthly:
        res = rpc.run_all([eth_call(C.WRBNT, BAL_OF + rpc.enc_address(a), b) for a in holders], workers=W)
        db.executemany("INSERT OR REPLACE INTO wrbnt VALUES (?,?,?)",
                       [(a, b, str(int(r, 16))) for a, r in zip(holders, res) if int(r, 16)])
        print(f"WRBNT at {lab}: {sum(1 for r in res if int(r, 16)):,} holders", flush=True)
    for lab, b in sorted(set(weekly) | set(monthly)):
        sup = int(rpc.call("eth_call", [{"to": C.WRBNT, "data": SUPPLY}, hex(b)]), 16)
        store.kv_set(db, f"wrbnt_supply_{b}", sup)
    db.commit()

    # Staked amounts.
    for pool in C.POOL_ADDRS:
        stakers = sorted(AD.pool_stakers(db, pool))
        store.kv_set(db, f"stakers_ever_{pool}", len(stakers))
        for lab, b in monthly:
            res = rpc.run_all([eth_call(pool, USER_INFO + rpc.enc_address(a), b) for a in stakers], workers=W)
            db.executemany("INSERT OR REPLACE INTO staked VALUES (?,?,?,?)",
                           [(pool, a, b, str(rpc.words(r)[0])) for a, r in zip(stakers, res) if rpc.words(r)[0]])
        for lab, b in sorted(set(weekly) | set(monthly)):
            ts = int(rpc.call("eth_call", [{"to": pool, "data": TOTAL_STAKE}, hex(b)]), 16)
            store.kv_set(db, f"total_stake_{pool}_{b}", ts)
        for lab, b in monthly:
            owner = rpc.call("eth_call", [{"to": pool, "data": OWNER}, hex(b)])
            store.kv_set(db, f"owner_{pool}_{b}", "0x" + owner[-40:])
        print(f"stakes read for {C.POOL_ADDRS[pool]} ({len(stakers):,} addresses ever staked)", flush=True)
    db.commit()

    # Lock calendar: when each open stake reaches the end of its lock, read at the end snapshot.
    end = [b for _, k, _, b, _ in snaps if "end" in k][0]
    for pool in C.POOL_ADDRS:
        open_stakers = [a for (a,) in db.execute("SELECT address FROM staked WHERE pool=? AND block=?", (pool, end))]
        res = rpc.run_all([eth_call(pool, UNLOCKS + rpc.enc_address(a), end) for a in open_stakers], workers=W)
        by_time = {}
        for r in res:
            wds = rpc.words(r)
            o1, o2 = wds[0] // 32, wds[1] // 32
            n = wds[o1]
            amounts, times = wds[o1 + 1:o1 + 1 + n], wds[o2 + 1:o2 + 1 + n]
            for amt, t in zip(amounts, times):
                by_time[t] = by_time.get(t, 0) + amt
        store.kv_set(db, f"unlocks_{pool}", json.dumps(sorted((t, str(v)) for t, v in by_time.items())))
    db.commit()

    # Contract or wallet: code at the end snapshot.
    end = [b for _, k, _, b, _ in snaps if "end" in k][0]
    holding = sorted({a for (a,) in db.execute("SELECT address FROM native UNION SELECT address FROM wrbnt "
                                               "UNION SELECT address FROM staked")})
    have = {a for (a,) in db.execute("SELECT address FROM code")}
    todo = [a for a in holding if a not in have]
    res = rpc.run_all([("eth_getCode", [a, hex(end)]) for a in todo], workers=W)
    rows = []
    for a, code in zip(todo, res):
        n = (len(code) - 2) // 2
        # EIP-7702 delegated accounts carry a 23 byte 0xef0100 marker; they are still key-controlled wallets.
        is_contract = 1 if n > 0 and not code.lower().startswith("0xef0100") else 0
        rows.append((a, end, is_contract, n))
    db.executemany("INSERT OR REPLACE INTO code VALUES (?,?,?,?)", rows)
    db.commit()
    print(f"code read for {len(todo):,} addresses; done")


if __name__ == "__main__":
    main()

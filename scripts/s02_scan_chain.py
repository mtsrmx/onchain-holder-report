"""Step 2. Read every transaction receipt from block 0 to the end snapshot.

From each receipt we keep:
  * every sender, recipient and created contract (to find every address),
  * the fee paid (gas used x effective gas price), summed per block,
  * the logs of the WRBNT contract and the two staking pools,
  * for blocks inside the quarter, the receipt itself.

The fee total matters: Redbelly blocks have no coinbase (miner is the zero
address), so fees leave circulation. Summed balances plus summed fees must
equal the 10 billion RBNT supply. That is the completeness check in step 9.
Resumable: progress is saved after each chunk.
"""
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from holder_report import config as C  # noqa: E402
from holder_report import rpc, store  # noqa: E402

WATCH = {C.WRBNT.lower()} | set(C.POOL_ADDRS)
STEP = 100      # blocks per request
CHUNK = 20000   # blocks per saved chunk
WORKERS = 24


MAX_TX = 1500   # receipts per request; some blocks carry 500 transfers each


def tx_counts(lo):
    hi = min(lo + STEP, END + 1)
    blocks = rpc.batch([("eth_getBlockByNumber", [hex(b), False]) for b in range(lo, hi)])
    return [(lo + i, len(b["transactions"])) for i, b in enumerate(blocks)]


def plan(counts):
    """Group blocks that have transactions into requests of at most MAX_TX receipts."""
    groups, cur, n = [], [], 0
    for b, c in counts:
        if c == 0:
            continue
        if cur and (n + c > MAX_TX or len(cur) == STEP):
            groups.append(cur)
            cur, n = [], 0
        cur.append(b)
        n += c
    if cur:
        groups.append(cur)
    return groups


def fetch(group):
    return group, rpc.batch([("eth_getBlockReceipts", [hex(b)]) for b in group])


def main():
    global END
    db = store.connect()
    snaps = {k: b for _, k, _, b, _ in store.snapshot_blocks(db)}
    q_start = [b for k, b in snaps.items() if "start" in k][0]
    END = [b for k, b in snaps.items() if "end" in k][0]
    nxt = int(store.get_progress(db, "scan_next", 0))
    t0 = time.time()
    first = nxt
    with ThreadPoolExecutor(WORKERS) as ex:
        while nxt <= END:
            hi = min(nxt + CHUNK, END + 1)
            counts = [x for part in ex.map(tx_counts, range(nxt, hi, STEP)) for x in part]
            results = list(ex.map(fetch, plan(counts)))
            n_expected = {b: c for b, c in counts}
            seen, fees, logs, rq = {}, [], [], []
            for group, blocks in results:
                for b, recs in zip(group, blocks):
                    if len(recs) != n_expected[b]:
                        raise RuntimeError(f"block {b}: {len(recs)} receipts for {n_expected[b]} transactions")
                    if not recs:
                        continue
                    fee = 0
                    for r in recs:
                        gu = int(r["gasUsed"], 16)
                        gp = int(r["effectiveGasPrice"], 16)
                        fee += gu * gp
                        frm, to, ca = r["from"].lower(), (r["to"] or "").lower(), (r["contractAddress"] or "").lower()
                        seen.setdefault(frm, (b, "tx_from"))
                        if to:
                            seen.setdefault(to, (b, "tx_to"))
                        if ca:
                            seen.setdefault(ca, (b, "created"))
                        if b > q_start:
                            rq.append((b, r["transactionHash"], int(r["transactionIndex"], 16), frm, to, ca,
                                       int(r["status"], 16), gu, str(gp)))
                        for lg in r["logs"]:
                            if lg["address"].lower() in WATCH:
                                t = lg["topics"] + [None] * (4 - len(lg["topics"]))
                                logs.append((b, lg["transactionHash"], int(lg["logIndex"], 16), lg["address"].lower(),
                                             t[0], t[1], t[2], t[3], lg["data"]))
                    fees.append((b, len(recs), str(fee)))
            db.executemany("INSERT OR IGNORE INTO seen VALUES (?,?,?)", [(a, b, h) for a, (b, h) in seen.items()])
            db.executemany("INSERT OR REPLACE INTO block_fees VALUES (?,?,?)", fees)
            db.executemany("INSERT OR IGNORE INTO logs VALUES (?,?,?,?,?,?,?,?,?)", logs)
            db.executemany("INSERT OR IGNORE INTO receipts_q VALUES (?,?,?,?,?,?,?,?,?)", rq)
            nxt = hi
            store.set_progress(db, "scan_next", nxt)
            db.commit()
            rate = (nxt - first) / max(1, time.time() - t0)
            print(f"scanned to {nxt - 1:,} of {END:,}  {rate:,.0f} blocks/s  eta {(END - nxt) / max(rate, 1) / 60:,.1f} min", flush=True)
    print("done")


if __name__ == "__main__":
    main()

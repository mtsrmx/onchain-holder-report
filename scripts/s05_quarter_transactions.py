"""Step 5. Read the value of every transaction inside the quarter.

Receipts (step 2) carry sender, recipient, status and fee but not the RBNT
value sent, so each block in the quarter is read once more with full
transactions. Together with internal transfers (step 3) this gives every RBNT
movement between the start and end snapshots.
Resumable.
"""
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from holder_report import rpc, store  # noqa: E402

STEP = 100
CHUNK = 10000


def fetch(lo_hi):
    lo, hi = lo_hi
    return rpc.batch([("eth_getBlockByNumber", [hex(b), True]) for b in range(lo, hi)])


def main():
    db = store.connect()
    snaps = store.snapshot_blocks(db)
    q_start = [b for _, k, _, b, _ in snaps if "start" in k][0]
    q_end = [b for _, k, _, b, _ in snaps if "end" in k][0]
    nxt = int(store.get_progress(db, "qtx_next", q_start + 1))
    t0 = time.time()
    with ThreadPoolExecutor(16) as ex:
        while nxt <= q_end:
            hi = min(nxt + CHUNK, q_end + 1)
            ranges = [(a, min(a + STEP, hi)) for a in range(nxt, hi, STEP)]
            rows = []
            for blocks in ex.map(fetch, ranges):
                for b in blocks:
                    for t in b["transactions"]:
                        rows.append((t["hash"], int(t["blockNumber"], 16), t["from"].lower(), (t["to"] or "").lower(),
                                     str(int(t["value"], 16)), t["input"][:10]))
            db.executemany("INSERT OR IGNORE INTO txs_q VALUES (?,?,?,?,?,?)", rows)
            nxt = hi
            store.set_progress(db, "qtx_next", nxt)
            db.commit()
            print(f"quarter transactions to block {nxt - 1:,} of {q_end:,} ({time.time() - t0:,.0f} s)", flush=True)
    rng = (q_start, q_end)
    n_r = db.execute("SELECT count(*) FROM receipts_q WHERE block > ? AND block <= ?", rng).fetchone()[0]
    n_t = db.execute("SELECT count(*) FROM txs_q WHERE block > ? AND block <= ?", rng).fetchone()[0]
    print(f"done: {n_t:,} transactions, {n_r:,} receipts")
    assert n_r == n_t, "every quarter transaction must have a receipt"


if __name__ == "__main__":
    main()

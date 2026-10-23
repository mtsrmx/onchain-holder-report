"""Step 2b. Read every block header and collect the addresses in its extraData.

Redbelly blocks carry the governor set in the header's extraData. Some of
these addresses hold RBNT without ever sending or receiving a transaction, so
they would be missed by step 2. They are added to the candidate list here.
Resumable.
"""
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from holder_report import rpc, store  # noqa: E402

STEP = 100
CHUNK = 50000


def rlp_items(data, out):
    """Collect every 20 byte string in an RLP structure."""
    i = 0
    while i < len(data):
        b = data[i]
        if b < 0x80:
            i += 1
        elif b <= 0xB7:
            n = b - 0x80
            if n == 20:
                out.add("0x" + data[i + 1:i + 21].hex())
            i += 1 + n
        elif b <= 0xBF:
            ln = b - 0xB7
            n = int.from_bytes(data[i + 1:i + 1 + ln], "big")
            i += 1 + ln + n
        elif b <= 0xF7:
            n = b - 0xC0
            rlp_items(data[i + 1:i + 1 + n], out)
            i += 1 + n
        else:
            ln = b - 0xF7
            n = int.from_bytes(data[i + 1:i + 1 + ln], "big")
            rlp_items(data[i + 1 + ln:i + 1 + ln + n], out)
            i += 1 + ln + n
    return out


def fetch(lo):
    hi = min(lo + STEP, END + 1)
    blocks = rpc.batch([("eth_getBlockByNumber", [hex(b), False]) for b in range(lo, hi)])
    found = {}
    for b in blocks:
        num = int(b["number"], 16)
        try:
            for a in rlp_items(bytes.fromhex(b["extraData"][2:]), set()):
                found.setdefault(a, num)
        except (IndexError, ValueError):
            pass
    return found


def main():
    global END
    db = store.connect()
    END = [b for _, k, _, b, _ in store.snapshot_blocks(db) if "end" in k][0]
    nxt = int(store.get_progress(db, "headers_next", 0))
    t0 = time.time()
    with ThreadPoolExecutor(24) as ex:
        while nxt <= END:
            hi = min(nxt + CHUNK, END + 1)
            found = {}
            for part in ex.map(fetch, range(nxt, hi, STEP)):
                for a, b in part.items():
                    found.setdefault(a, b)
            db.executemany("INSERT OR IGNORE INTO seen VALUES (?,?,?)", [(a, b, "block_header") for a, b in found.items()])
            nxt = hi
            store.set_progress(db, "headers_next", nxt)
            db.commit()
            n = db.execute("SELECT count(*) FROM seen WHERE how='block_header'").fetchone()[0]
            print(f"headers to {nxt - 1:,}: {n:,} header-only addresses ({time.time() - t0:,.0f} s)", flush=True)
    print("done")


if __name__ == "__main__":
    main()

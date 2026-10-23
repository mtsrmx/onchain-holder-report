"""Step 3. Read every internal transfer from the explorer, block 0 to the end snapshot.

An internal transfer is RBNT moved by a contract (for example the WRBNT
contract paying out on unwrap). The public node has no trace API, so these
come from Routescan's txlistinternal call, paged by block range.
Resumable.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from holder_report import explorer, store  # noqa: E402

PAGE = 10000


def main():
    db = store.connect()
    end = [b for _, k, _, b, _ in store.snapshot_blocks(db) if "end" in k][0]
    start = int(store.get_progress(db, "internal_next", 0))
    while start <= end:
        page = 1
        while True:
            rows = explorer.api(module="account", action="txlistinternal", startblock=start, endblock=end,
                                page=page, offset=PAGE, sort="asc")
            db.executemany("INSERT OR IGNORE INTO internal VALUES (?,?,?,?,?,?,?,?,?)", [
                (int(r["blockNumber"]), r["hash"], r["traceId"], r["from"].lower(), (r["to"] or "").lower(),
                 r["value"], r["type"], (r["contractAddress"] or "").lower(), int(r["isError"] or 0)) for r in rows])
            db.commit()
            if len(rows) < PAGE:
                start = end + 1
                break
            last = int(rows[-1]["blockNumber"])
            if last > start:
                # Re-read from the last block so no transfer in it is cut off; duplicates are ignored.
                start = last
                break
            page += 1  # one block holds more than a page
        store.set_progress(db, "internal_next", start)
        db.commit()
        n = db.execute("SELECT count(*) FROM internal").fetchone()[0]
        print(f"internal transfers up to block {start:,}: {n:,}", flush=True)
    store.set_progress(db, "internal_next", end + 1)
    db.commit()
    print("done")


if __name__ == "__main__":
    main()

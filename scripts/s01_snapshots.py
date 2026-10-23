"""Step 1. Find the block for every snapshot time.

A snapshot at time T is the last block whose timestamp is before T, found by
binary search on the Redbelly node. The result is cross-checked against the
explorer's getblocknobytime call.
"""
import sys
from datetime import datetime, timezone

import requests

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))
from holder_report import config as C  # noqa: E402
from holder_report import rpc, store  # noqa: E402


def iso(ts):
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%MZ")


def main():
    db = store.connect()
    tags = {}
    for t in C.WEEKLY_TS:
        tags.setdefault(t, set()).add("week")
    for t in C.MONTHLY_TS:
        tags.setdefault(t, set()).add("month")
    tags.setdefault(C.QUARTER["start_ts"], set()).add("start")
    tags.setdefault(C.QUARTER["end_ts"], set()).add("end")
    head = rpc.head()
    for t in sorted(tags):
        b = rpc.last_block_before(t, hi=head)
        bts = rpc.block_ts(b)
        nxt = rpc.block_ts(b + 1)
        assert bts < t <= nxt, (t, b, bts, nxt)
        r = requests.get(C.EXPLORER_API, params={"module": "block", "action": "getblocknobytime",
                                                  "timestamp": t - 1, "closest": "before"}, timeout=60).json()
        explorer_b = int(r["result"]) if r.get("status") == "1" else None
        kind = ",".join(sorted(tags[t]))
        db.execute("INSERT OR REPLACE INTO snapshots VALUES (?,?,?,?,?)", (iso(t), kind, t, b, bts))
        print(f"{iso(t)}  block {b:,}  block time {iso(bts)}  [{kind}]  explorer says {explorer_b}")
        if explorer_b is not None and explorer_b != b:
            print("   note: explorer block differs from node binary search")
    db.commit()


if __name__ == "__main__":
    main()

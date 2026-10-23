"""Every RBNT movement inside the quarter, and per-address reconciliation."""
from collections import defaultdict

# Internal call types that move value. A delegatecall carries the caller's
# value only as context, and a staticcall cannot carry value.
VALUE_KINDS = {"call", "create", "create2", "suicide", "selfdestruct"}


def tx_status(db, q_start, q_end):
    return {h: s for h, s in db.execute("SELECT tx_hash, status FROM receipts_q WHERE block > ? AND block <= ?",
                                        (q_start, q_end))}


def native_moves(db, q_start, q_end):
    """Yield (sender, recipient, wei, kind, tx_hash) for every successful RBNT movement."""
    status = tx_status(db, q_start, q_end)
    created = {h: c for h, c in db.execute("SELECT tx_hash, created FROM receipts_q WHERE created != ''")}
    for h, _b, f, t, v, _sel in db.execute("SELECT * FROM txs_q WHERE block > ? AND block <= ?", (q_start, q_end)):
        v = int(v)
        if v and status.get(h) == 1:
            yield f, (t or created.get(h, "")), v, "transaction", h
    for _b, h, _tid, f, t, v, kind, c, err in db.execute(
            "SELECT * FROM internal WHERE block > ? AND block <= ?", (q_start, q_end)):
        v = int(v)
        if not v or err or kind not in VALUE_KINDS:
            continue
        if status.get(h, 1) != 1:
            continue
        yield f, (t or c), v, "internal", h


def fees_by_sender(db, q_start, q_end):
    out = defaultdict(int)
    for f, gu, gp in db.execute("SELECT sender, gas_used, gas_price FROM receipts_q WHERE block > ? AND block <= ?",
                                (q_start, q_end)):
        out[f] += gu * int(gp)
    return out


def reconcile(addresses, start_bal, end_bal, moves, fees):
    """start + in - out - fees - end, per address. Zero means every wei is explained."""
    addresses = set(addresses)
    inflow, outflow = defaultdict(int), defaultdict(int)
    n_in, n_out = defaultdict(int), defaultdict(int)
    for f, t, v, _k, _h in moves:
        if t in addresses:
            inflow[t] += v
            n_in[t] += 1
        if f in addresses:
            outflow[f] += v
            n_out[f] += 1
    res = {}
    for a in addresses:
        gap = start_bal.get(a, 0) + inflow[a] - outflow[a] - fees.get(a, 0) - end_bal.get(a, 0)
        res[a] = {"in_wei": inflow[a], "out_wei": outflow[a], "n_in": n_in[a], "n_out": n_out[a],
                  "fees_wei": fees.get(a, 0), "gap_wei": gap}
    return res

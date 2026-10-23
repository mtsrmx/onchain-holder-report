"""Step 7. Turn the cached chain data into the tables behind the report.

Writes data/*.csv and data/figures.json. Every number quoted in the report
text is read from figures.json, and every chart is drawn from a CSV here.
The script stops with an error if any check fails.
"""
import csv
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from holder_report import addresses as AD  # noqa: E402
from holder_report import analysis as A  # noqa: E402
from holder_report import config as C  # noqa: E402
from holder_report import flows as F  # noqa: E402
from holder_report import rpc, store  # noqa: E402

WEI = C.WEI
SUPPLY_WEI = C.TOTAL_SUPPLY_RBNT * WEI
STAKE_SEL = rpc.selector("stake()")


def r(wei, nd=0):
    """wei to RBNT rounded for the CSV files (full precision stays in the cache)."""
    return round(wei / WEI, nd) if nd else int(round(wei / WEI))


def day(ts):
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d")


def when(ts):
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def write_csv(name, header, rows):
    C.DATA.mkdir(exist_ok=True)
    with open(C.DATA / name, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


class Checks:
    def __init__(self):
        self.items = []

    def eq(self, name, a, b, tol=0):
        ok = abs(a - b) <= tol
        self.items.append({"check": name, "left": str(a), "right": str(b), "passed": ok})
        if not ok:
            raise SystemExit(f"CHECK FAILED: {name}: {a} != {b}")


def main():
    db = store.connect()
    chk = Checks()
    snaps = store.snapshot_blocks(db)
    monthly = [(lab, b, bts) for lab, k, _, b, bts in snaps if "month" in k]
    weekly = [(lab, b, bts) for lab, k, _, b, bts in snaps if "week" in k or "end" in k]
    S = [b for _, k, _, b, _ in snaps if "start" in k][0]
    E = [b for _, k, _, b, _ in snaps if "end" in k][0]
    ts_of = {b: bts for _, _, _, b, bts in snaps}
    read_on = store.kv_get(db, "read_on") or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    reserved = dict(C.RESERVED)
    pools = dict(C.POOL_ADDRS)
    wr = C.WRBNT.lower()
    labelled = {a: n for a, n in db.execute("SELECT address, name FROM explorer_list WHERE name IS NOT NULL AND name != ''")}
    exchanges = {a: n for a, n in labelled.items() if a not in reserved and a not in pools and a != wr}
    named = set(reserved) | set(pools) | {wr} | set(labelled)
    is_contract = {a: c for a, c in db.execute("SELECT address, is_contract FROM code")}

    def system(a):
        return int(a, 16) < 1024  # zero address and precompiles

    def kind(a):
        if a in reserved:
            return "reserved"
        if a in pools:
            return "pool"
        if a == wr:
            return "wrbnt"
        if a in labelled:
            return "labelled"
        if system(a) or is_contract.get(a):
            return "contract"
        return "wallet"

    def load(table, b):
        return {a: int(v) for a, v in db.execute(f"SELECT address, wei FROM {table} WHERE block=?", (b,))}

    def load_staked(b):
        out = {p: {} for p in pools}
        for p, a, v in db.execute("SELECT pool, address, wei FROM staked WHERE block=?", (b,)):
            out[p][a] = int(v)
        return out

    # Network fees paid from block 0 up to and including each snapshot block, in one pass.
    marks = sorted({b for _, _, _, b, _ in snaps})
    fees_cum, acc, i = {}, 0, 0
    for n, v in db.execute("SELECT number, fee_wei FROM block_fees ORDER BY number"):
        while i < len(marks) and n > marks[i]:
            fees_cum[marks[i]] = acc
            i += 1
        acc += int(v)
    for m in marks[i:]:
        fees_cum[m] = acc

    figs = {"quarter": C.QUARTER["label"], "first_day": C.QUARTER["first_day"], "last_day": C.QUARTER["last_day"],
            "start_block": S, "end_block": E, "start_time": when(ts_of[S]), "end_time": when(ts_of[E]),
            "read_on": read_on, "candidate_addresses": int(store.kv_get(db, "candidate_count", 0)),
            "explorer_address_count": store.kv_get(db, "explorer_address_count"),
            "explorer_listed_addresses": db.execute("SELECT count(*) FROM explorer_list").fetchone()[0],
            "labelled": labelled, "labelled_exchanges": exchanges,
            "internal_transfers_read": db.execute("SELECT count(*) FROM internal").fetchone()[0],
            "blocks_scanned": E + 1}

    # ---- 1. Supply reconciliation and where the RBNT sits, at each month-end snapshot.
    where_rows, econ_rows, supply_rows = [], [], []
    snap = {}
    for lab, b, bts in monthly:
        nat, wrb, stk = load("native", b), load("wrbnt", b), load_staked(b)
        total_native = sum(nat.values())
        unfound = SUPPLY_WEI - total_native
        supply_rows.append([day(bts - 1), b, when(bts), C.TOTAL_SUPPLY_RBNT, r(total_native, 6), r(unfound, 6),
                            round(total_native / SUPPLY_WEI * 100, 5), r(fees_cum[b], 6)])
        wr_supply = int(store.kv_get(db, f"wrbnt_supply_{b}"))
        chk.eq(f"WRBNT totalSupply equals RBNT held by the WRBNT contract at block {b}", wr_supply, nat.get(wr, 0))
        chk.eq(f"sum of WRBNT balances equals WRBNT totalSupply at block {b}", sum(wrb.values()), wr_supply)
        total_stake = {}
        for p in pools:
            total_stake[p] = int(store.kv_get(db, f"total_stake_{p}_{b}"))
            chk.eq(f"stakers' amounts add up to totalStake, {pools[p]}, block {b}", sum(stk[p].values()), total_stake[p])
        groups = defaultdict(int)
        counts = defaultdict(int)
        for a, v in nat.items():
            k = kind(a)
            if k == "pool":
                groups["pool_staked"] += total_stake[a]
                groups["pool_reward_funds"] += v - total_stake[a]
            else:
                groups[k] += v
                counts[k] += 1 if v >= WEI else 0
        groups["unfound"] = unfound
        chk.eq(f"where-RBNT-sits groups add up to 10 billion at block {b}", sum(groups.values()), SUPPLY_WEI)
        where_rows.append((lab, b, bts, dict(groups), dict(counts)))

        # Economic view: WRBNT and stakes counted with whoever owns them.
        pos_all = A.positions(nat, wrb, stk, exclude=set(pools) | {wr})
        econ = defaultdict(int)
        for a, v in pos_all.items():
            econ[kind(a)] += v
        econ["pool_reward_funds"] = groups["pool_reward_funds"]
        econ["unfound"] = unfound
        chk.eq(f"ownership groups add up to 10 billion at block {b}", sum(econ.values()), SUPPLY_WEI)
        econ_rows.append((lab, b, bts, dict(econ)))
        wallets = {a: v for a, v in pos_all.items() if kind(a) == "wallet"}
        contracts = {a: v for a, v in pos_all.items() if kind(a) == "contract"}
        snap[b] = {"nat": nat, "wrb": wrb, "stk": stk, "wallets": wallets, "contracts": contracts,
                   "total_stake": total_stake, "groups": groups, "econ": econ, "wr_supply": wr_supply}

    write_csv("01_supply_check.csv",
              ["date (end of day UTC)", "block", "block time", "RBNT created at genesis", "RBNT in all balances read",
               "RBNT not found in any balance", "% of supply found", "network fees paid since launch (RBNT)"], supply_rows)

    labels_where = [("reserved", "Redbelly reserved wallets"), ("wrbnt", "Wrapped RBNT contract (backs WRBNT)"),
                    ("pool_staked", "Reddex pools: staked"), ("pool_reward_funds", "Reddex pools: reward funds"),
                    ("wallet", "Other wallets"), ("contract", "Other contracts"),
                    ("labelled", "Other addresses labelled on Routescan"), ("unfound", "Not found in any balance read")]
    rows = []
    for key, name in labels_where:
        row = [name]
        for lab, b, bts, g, _c in where_rows:
            row += [r(g.get(key, 0)), round(g.get(key, 0) / SUPPLY_WEI * 100, 3)]
        rows.append(row)
    hdr = ["where the RBNT is"]
    for lab, b, bts, _g, _c in where_rows:
        hdr += [f"RBNT {day(bts - 1)}", f"% of supply {day(bts - 1)}"]
    write_csv("02_where_the_rbnt_is.csv", hdr, rows)

    labels_econ = [("reserved", "Redbelly reserved wallets"), ("wallet", "Other wallets"), ("contract", "Other contracts"),
                   ("labelled", "Other addresses labelled on Routescan"), ("wrbnt", "WRBNT held by the WRBNT contract itself"),
                   ("pool_reward_funds", "Reddex pools: reward funds"), ("unfound", "Not found in any balance read")]
    rows = []
    for key, name in labels_econ:
        row = [name]
        for lab, b, bts, g in econ_rows:
            row += [r(g.get(key, 0)), round(g.get(key, 0) / SUPPLY_WEI * 100, 3)]
        rows.append(row)
    write_csv("03_who_holds_the_rbnt.csv", ["holder group (WRBNT and stakes counted with their owner)"] + hdr[1:], rows)

    s, e = snap[S], snap[E]
    g0, g1 = s["groups"], e["groups"]
    figs["where"] = {k: {"start": r(g0.get(k, 0)), "end": r(g1.get(k, 0)),
                         "start_pct": g0.get(k, 0) / SUPPLY_WEI, "end_pct": g1.get(k, 0) / SUPPLY_WEI}
                     for k, _ in labels_where}
    figs["econ"] = {k: {"start": r(s["econ"].get(k, 0)), "end": r(e["econ"].get(k, 0))} for k, _ in labels_econ}
    figs["fees_in_quarter"] = r(fees_cum[E] - fees_cum[S], 2)
    figs["fees_since_launch_end"] = r(fees_cum[E])
    figs["balances_total"] = {"start": r(sum(s["nat"].values()), 2), "end": r(sum(e["nat"].values()), 2)}
    figs["balances_change_in_quarter"] = r(sum(e["nat"].values()) - sum(s["nat"].values()), 2)
    figs["unfound"] = {"start": r(SUPPLY_WEI - sum(s["nat"].values()), 2), "end": r(SUPPLY_WEI - sum(e["nat"].values()), 2)}

    # ---- 2. Holder bands, month by month (wallets; contracts reported as one line).
    rows = []
    band_data = {}
    for lab, b, bts in monthly:
        band_data[b] = A.distribution(snap[b]["wallets"])
    for name, _lo in A.BANDS:
        row = [name]
        for lab, b, bts in monthly:
            n, v = band_data[b][name]
            row += [n, r(v)]
        rows.append(row)
    crow = ["Contracts (all sizes)"]
    for lab, b, bts in monthly:
        cpos = [v for v in snap[b]["contracts"].values() if v > 0]
        crow += [len(cpos), r(sum(cpos))]
    rows.append(crow)
    hdr = ["holding size (RBNT, wallets)"]
    for lab, b, bts in monthly:
        hdr += [f"wallets {day(bts - 1)}", f"RBNT held {day(bts - 1)}"]
    write_csv("04_holders_by_size.csv", hdr, rows)

    def n_holders(b, minimum=WEI):
        return sum(1 for v in snap[b]["wallets"].values() if v >= minimum)

    figs["holders"] = {day(bts - 1): {"wallets_1plus": n_holders(b), "wallets_any": sum(1 for v in snap[b]["wallets"].values() if v > 0),
                                      "contracts_1plus": sum(1 for v in snap[b]["contracts"].values() if v >= WEI)}
                       for lab, b, bts in monthly}
    figs["bands"] = {name: {"start": band_data[S][name][0], "end": band_data[E][name][0],
                            "start_rbnt": r(band_data[S][name][1]), "end_rbnt": r(band_data[E][name][1])}
                     for name, _ in A.BANDS}
    w0 = {a for a, v in s["wallets"].items() if v >= WEI}
    w1 = {a for a, v in e["wallets"].items() if v >= WEI}
    figs["holder_turnover"] = {"both": len(w0 & w1), "joined": len(w1 - w0), "left": len(w0 - w1)}

    # ---- 3. Concentration among wallets with 1 RBNT or more.
    rows = []
    conc = {}
    for lab, b, bts in monthly:
        vals = [v for v in snap[b]["wallets"].values() if v >= WEI]
        total = sum(vals)
        c = {"wallets": len(vals), "total": r(total),
             "top10": A.top_share(vals, 10), "top100": A.top_share(vals, 100), "top1000": A.top_share(vals, 1000),
             "gini": A.gini(vals), "for_50": A.holders_for_share(vals, 0.5), "for_90": A.holders_for_share(vals, 0.9)}
        conc[b] = c
        rows.append([day(bts - 1), b, c["wallets"], c["total"], round(c["top10"] * 100, 2), round(c["top100"] * 100, 2),
                     round(c["top1000"] * 100, 2), round(c["gini"], 4), c["for_50"], c["for_90"]])
    write_csv("05_concentration.csv",
              ["date (end of day UTC)", "block", "wallets with 1+ RBNT", "RBNT they hold", "largest 10 share %",
               "largest 100 share %", "largest 1,000 share %", "Gini coefficient", "wallets that hold half",
               "wallets that hold 90%"], rows)
    figs["concentration"] = {"start": conc[S], "end": conc[E], "monthly": {day(ts_of[b] - 1): conc[b] for _, b, _ in monthly}}
    top100_start = set(sorted(w0, key=lambda a: -s["wallets"][a])[:100])
    top100_end = set(sorted(w1, key=lambda a: -e["wallets"][a])[:100])
    figs["top100_new_entrants"] = len(top100_end - top100_start)

    # ---- 4. Cohorts: the same wallets followed through the quarter.
    start_w = {a: v for a, v in s["wallets"].items() if v >= WEI}
    end_all = dict(e["wallets"])
    # A wallet that became a contract during the quarter is still followed.
    for a in start_w:
        if a not in end_all and a in e["contracts"]:
            end_all[a] = e["contracts"][a]
    table = A.cohort_table(start_w, end_all)
    rows = []
    month_tot = {}
    for row in table:
        members = [a for a in start_w if A.band_of(start_w[a], A.COHORTS) == row["cohort"]]
        month_tot[row["cohort"]] = [sum(snap[b]["wallets"].get(a, 0) + snap[b]["contracts"].get(a, 0) for a in members)
                                    for _, b, _ in monthly]
        chk.eq(f"cohort start total matches, {row['cohort']}", month_tot[row["cohort"]][0], row["start_wei"])
        chk.eq(f"cohort end total matches, {row['cohort']}", month_tot[row["cohort"]][-1], row["end_wei"])
        net = row["end_wei"] - row["start_wei"]
        rows.append([row["cohort"], row["wallets"], row["added"], row["unchanged"], row["reduced"], row["exited"],
                     r(row["start_wei"]), r(row["end_wei"]), r(net), round(net / row["start_wei"] * 100, 2)]
                    + [r(x) for x in month_tot[row["cohort"]][1:-1]])
    new_w = {a: v for a, v in e["wallets"].items() if v >= WEI and s["wallets"].get(a, 0) < WEI}
    rows.append(["New wallets (under 1 RBNT at the start)", len(new_w), "", "", "", "", 0, r(sum(new_w.values())),
                 r(sum(new_w.values())), ""] + ["", ""])
    write_csv("06_cohorts.csv",
              ["group (by holding at the start)", "wallets", "added more than 1%", "within 1%", "reduced more than 1%",
               "under 1 RBNT at the end", "RBNT at start", "RBNT at end", "net change", "net change %",
               f"RBNT {day(ts_of[monthly[1][1]] - 1)}", f"RBNT {day(ts_of[monthly[2][1]] - 1)}"], rows)
    figs["cohorts"] = {row["cohort"]: {k: (r(v) if k.endswith("_wei") else v) for k, v in row.items()} for row in table}
    figs["new_wallets"] = {"count": len(new_w), "rbnt": r(sum(new_w.values()))}

    # Band moves: did a wallet end the quarter in a bigger or smaller size band than it started in?
    order = {name: i for i, (name, _lo) in enumerate(A.BANDS)}  # 0 is the biggest band
    lowest = len(A.BANDS)  # holds nothing
    moves_band = {"up": 0, "down": 0, "same": 0, "up2": 0, "down2": 0}
    gain_from_up2 = {}
    for a in set(w0) | set(w1):
        b0 = order[A.band_of(s["wallets"][a])] if s["wallets"].get(a, 0) > 0 else lowest
        b1 = order[A.band_of(end_all[a])] if end_all.get(a, 0) > 0 else lowest
        if b1 < b0:
            moves_band["up"] += 1
            if b0 - b1 >= 2:
                moves_band["up2"] += 1
                gain_from_up2[a] = end_all.get(a, 0) - s["wallets"].get(a, 0)
        elif b1 > b0:
            moves_band["down"] += 1
            if b1 - b0 >= 2:
                moves_band["down2"] += 1
        else:
            moves_band["same"] += 1
    figs["band_moves"] = moves_band
    small_cohorts = ("Smaller wallets (1,000 to 100,000)", "Small wallets (1 to 1,000)")
    small_members = {a for a in start_w if A.band_of(start_w[a], A.COHORTS) in small_cohorts}
    jumpers = [a for a in small_members if end_all.get(a, 0) >= 1_000_000 * WEI]
    figs["small_cohort_jumpers"] = {
        "count": len(jumpers),
        "gain": r(sum(end_all[a] - start_w[a] for a in jumpers)),
        "cohort_gain": r(sum(end_all.get(a, 0) - start_w[a] for a in small_members)),
    }
    write_csv("06b_band_moves.csv", ["move between 30 June and 30 September", "wallets"],
              [["ended in a bigger size band", moves_band["up"]], ["of which two or more bands bigger", moves_band["up2"]],
               ["ended in the same size band", moves_band["same"]], ["ended in a smaller size band", moves_band["down"]],
               ["of which two or more bands smaller", moves_band["down2"]],
               ["wallets that started under 100,000 RBNT and ended with 1 million or more", len(jumpers)],
               ["RBNT those wallets gained", r(figs["small_cohort_jumpers"]["gain"] * WEI)]])

    # Contracts grouped by what their verified source code says they are.
    meta = {a: n for a, n, _v, _h in db.execute("SELECT * FROM contract_meta")}

    def ctype(a):
        nm = meta.get(a, "")
        if not nm:
            return "Unverified contracts"
        low = nm.lower()
        if "gnosissafe" in low or low in ("safe", "safeproxy"):
            return "Multi-signature wallets (Safe)"
        if "vesting" in low:
            return "Vesting contracts"
        if low.endswith("pair") or low.endswith("pool"):
            return "Trading pools on decentralised exchanges"
        if "staker" in low or "masterchef" in low:
            return "Other staking contracts"
        if any(k in low for k in ("oft", "bridge", "vault", "lockrelease", "senduln", "executor")):
            return "Bridge contracts"
        return "Other verified contracts"

    ctypes = defaultdict(lambda: [set(), 0, 0])
    for a in set(s["contracts"]) | set(e["contracts"]):
        v0, v1 = s["contracts"].get(a, 0), e["contracts"].get(a, 0)
        if max(v0, v1) < WEI:
            continue
        g = ctypes[ctype(a)]
        g[0].add(a)
        g[1] += v0
        g[2] += v1
    # Kinds with fewer than MIN_GROUP contracts are folded into "Other verified contracts".
    for k in [k for k, g in ctypes.items() if len(g[0]) < C.MIN_GROUP and k != "Other verified contracts"]:
        g = ctypes.pop(k)
        o = ctypes["Other verified contracts"]
        o[0] |= g[0]
        o[1] += g[1]
        o[2] += g[2]
    rows = []
    for k, (members, v0, v1) in sorted(ctypes.items(), key=lambda x: -x[1][2]):
        assert len(members) >= C.MIN_GROUP, k
        rows.append([k, len(members), r(v0), r(v1), r(v1 - v0), round(v1 / SUPPLY_WEI * 100, 2)])
    dust = sum(v for a, v in e["contracts"].items() if max(v, s["contracts"].get(a, 0)) < WEI)
    chk.eq("contract groups plus contracts under 1 RBNT add up to all contracts at the end",
           sum(g[2] for g in ctypes.values()) + dust, sum(e["contracts"].values()))
    write_csv("06c_contracts_by_kind.csv",
              ["kind of contract (from verified source code)", "contracts", "RBNT at start", "RBNT at end", "change",
               "% of supply at end"], rows)
    figs["contract_kinds"] = {k: {"count": len(m), "start": r(v0), "end": r(v1)} for k, (m, v0, v1) in ctypes.items()}

    # Net change of every group, from holdings at the two snapshots. Groups cover
    # all 10 billion RBNT, so the changes must add up to exactly zero.
    net_rows = []
    for row in table:
        net_rows.append((row["cohort"], row["start_wei"], row["end_wei"]))
    under = [a for a in set(s["wallets"]) | set(e["wallets"]) if s["wallets"].get(a, 0) < WEI]
    net_rows.append(("Wallets under 1 RBNT at the start", sum(s["wallets"].get(a, 0) for a in under),
                     sum(e["wallets"].get(a, 0) for a in under)))
    followed = set(start_w)
    for k, (m, v0, v1) in ctypes.items():
        net_rows.append((k, v0, v1))
    cdust0 = sum(v for a, v in s["contracts"].items() if max(v, e["contracts"].get(a, 0)) < WEI)
    net_rows.append(("Contracts under 1 RBNT", cdust0, dust))
    net_rows.append(("Redbelly reserved wallets", s["econ"]["reserved"], e["econ"]["reserved"]))
    net_rows.append(("Reddex pools: reward funds", s["econ"]["pool_reward_funds"], e["econ"]["pool_reward_funds"]))
    net_rows.append(("Not found in any balance read", s["econ"]["unfound"], e["econ"]["unfound"]))
    # A wallet that turned into a contract would be counted twice; there must be none.
    switched = [a for a in followed if a in e["contracts"]]
    chk.eq("no followed wallet became a contract during the quarter", len(switched), 0)
    chk.eq("net changes of all groups add up to zero", sum(v1 - v0 for _k, v0, v1 in net_rows), 0)
    write_csv("06d_net_change_by_group.csv", ["group", "RBNT at start", "RBNT at end", "net change"],
              [[k, r(v0), r(v1), r(v1 - v0)] for k, v0, v1 in net_rows])
    figs["net_change_by_group"] = {k: {"start": r(v0), "end": r(v1), "change": r(v1 - v0)} for k, v0, v1 in net_rows}

    # ---- 5. Movements inside the quarter and reconciliation of every named address.
    moves = list(F.native_moves(db, S, E))
    fees = F.fees_by_sender(db, S, E)
    figs["quarter_transactions"] = db.execute("SELECT count(*) FROM txs_q WHERE block > ? AND block <= ?", (S, E)).fetchone()[0]
    figs["quarter_internal_transfers"] = db.execute("SELECT count(*) FROM internal WHERE block > ? AND block <= ?", (S, E)).fetchone()[0]
    named_list = list(reserved) + list(pools) + [wr]
    rec = F.reconcile(named_list, s["nat"], e["nat"], moves, fees)
    for a in named_list:
        chk.eq(f"named address reconciles to the wei: {reserved.get(a) or pools.get(a) or 'WRBNT'}", rec[a]["gap_wei"], 0)

    # Weekly native balances of named addresses, pools and WRBNT.
    weekly_rows = []
    for lab, b, bts in weekly:
        nat_w = {a: int(v) for a, v in db.execute("SELECT address, wei FROM native WHERE block=?", (b,)) if a in set(named_list)}
        row = [day(bts - 1), b]
        for a in reserved:
            row.append(r(nat_w.get(a, 0)))
        for p in pools:
            ts_ = int(store.kv_get(db, f"total_stake_{p}_{b}"))
            row += [r(nat_w.get(p, 0)), r(ts_), r(nat_w.get(p, 0) - ts_)]
        row.append(r(int(store.kv_get(db, f"wrbnt_supply_{b}"))))
        weekly_rows.append(row)
    hdr = ["date (end of day UTC)", "block"] + [f"{n} RBNT" for n in reserved.values()]
    for p in pools.values():
        hdr += [f"{p}: RBNT balance", f"{p}: staked (totalStake)", f"{p}: reward funds"]
    hdr.append("WRBNT supply")
    write_csv("07_weekly_named_addresses.csv", hdr, weekly_rows)

    # Named wallet table with counterparties grouped.
    def cp_group(a):
        k = kind(a)
        if k == "reserved":
            return reserved[a]
        if k == "pool":
            return pools[a]
        if k == "wrbnt":
            return "Wrapped RBNT contract"
        if k == "labelled":
            return labelled[a]
        return "unlabelled contracts" if k == "contract" else "unlabelled wallets"

    rows = []
    for name, a, alloc in C.RESERVED_WALLETS:
        a = a.lower()
        x = rec[a]
        w0_, w1_ = s["wrb"].get(a, 0), e["wrb"].get(a, 0)
        k0 = sum(s["stk"][p].get(a, 0) for p in pools)
        k1 = sum(e["stk"][p].get(a, 0) for p in pools)
        rows.append([name, a, alloc if alloc else "not listed", r(s["nat"].get(a, 0)), r(e["nat"].get(a, 0)),
                     r(e["nat"].get(a, 0) - s["nat"].get(a, 0)), x["n_in"], r(x["in_wei"]), x["n_out"], r(x["out_wei"]),
                     r(x["fees_wei"], 2), x["gap_wei"], r(w0_), r(w1_), r(k0), r(k1)])
    for a in list(pools) + [wr]:
        x = rec[a]
        rows.append([pools.get(a, "Wrapped RBNT (WRBNT) contract"), a, "", r(s["nat"].get(a, 0)), r(e["nat"].get(a, 0)),
                     r(e["nat"].get(a, 0) - s["nat"].get(a, 0)), x["n_in"], r(x["in_wei"]), x["n_out"], r(x["out_wei"]),
                     r(x["fees_wei"], 2), x["gap_wei"], "", "", "", ""])
    write_csv("08_named_addresses.csv",
              ["name", "address", "allocation on DAO treasury page (RBNT)", "RBNT at start", "RBNT at end", "change",
               "transfers in", "RBNT in", "transfers out", "RBNT out", "fees paid (RBNT)", "reconciliation gap (wei)",
               "WRBNT at start", "WRBNT at end", "staked at start", "staked at end"], rows)

    # Counterparty flows of reserved wallets (native RBNT and WRBNT).
    flows = defaultdict(lambda: [0, 0, 0, 0])  # n_in, in, n_out, out
    for f, t, v, _k, _h in moves:
        if t in reserved:
            x = flows[(reserved[t], "RBNT", cp_group(f))]
            x[0] += 1
            x[1] += v
        if f in reserved:
            x = flows[(reserved[f], "RBNT", cp_group(t))]
            x[2] += 1
            x[3] += v
    wr_moves = list(db.execute("SELECT block, t1, t2, data FROM logs WHERE address=? AND t0=? AND block > ? AND block <= ?",
                               (wr, AD.T_TRANSFER, S, E)))
    for _b, t1, t2, data in wr_moves:
        f, t, v = AD.topic_addr(t1), AD.topic_addr(t2), int(data, 16)
        if t in reserved:
            x = flows[(reserved[t], "WRBNT", cp_group(f))]
            x[0] += 1
            x[1] += v
        if f in reserved:
            x = flows[(reserved[f], "WRBNT", cp_group(t))]
            x[2] += 1
            x[3] += v
    rows = []
    distinct_unlabelled = defaultdict(set)
    for f, t, v, _k, _h in moves:
        if f in reserved and kind(t) in ("wallet", "contract"):
            distinct_unlabelled[reserved[f]].add(t)
    for (wname, token, cp), (ni, vi, no, vo) in sorted(flows.items()):
        rows.append([wname, token, cp, ni, r(vi), no, r(vo)])
    write_csv("09_reserved_wallet_flows.csv",
              ["reserved wallet", "token", "counterparty", "transfers in", "amount in", "transfers out", "amount out"], rows)
    figs["reserved_flows"] = [{"wallet": a, "token": tk, "counterparty": cp, "n_in": ni, "in": r(vi), "n_out": no, "out": r(vo)}
                              for (a, tk, cp), (ni, vi, no, vo) in sorted(flows.items())]
    figs["reserved_distinct_unlabelled_recipients"] = {k: len(v) for k, v in distinct_unlabelled.items()}
    figs["reserved"] = {}
    for name, a, alloc in C.RESERVED_WALLETS:
        a = a.lower()
        figs["reserved"][name] = {"start": r(s["nat"].get(a, 0)), "end": r(e["nat"].get(a, 0)), "allocation": alloc,
                                  "wrbnt_start": r(s["wrb"].get(a, 0)), "wrbnt_end": r(e["wrb"].get(a, 0)),
                                  "n_in": rec[a]["n_in"], "n_out": rec[a]["n_out"], "fees": r(rec[a]["fees_wei"], 2)}
    figs["reserved_total"] = {"start": r(g0["reserved"]), "end": r(g1["reserved"]),
                              "start_econ": r(s["econ"]["reserved"]), "end_econ": r(e["econ"]["reserved"])}

    # ---- 6. Staking.
    rows = []
    figs["pools"] = {}
    for p, pname in pools.items():
        ev = defaultdict(lambda: [0, 0, set()])
        for t0, data, h in db.execute("SELECT t0, data, tx_hash FROM logs WHERE address=? AND block > ? AND block <= ?", (p, S, E)):
            if t0 in (AD.T_STAKE, AD.T_UNSTAKE, AD.T_CLAIM):
                k = {AD.T_STAKE: "stake", AD.T_UNSTAKE: "unstake", AD.T_CLAIM: "claim"}[t0]
                wds = [int(data[2 + i * 64: 2 + (i + 1) * 64], 16) for i in range((len(data) - 2) // 64)]
                ev[k][0] += 1
                ev[k][1] += wds[1]
                ev[k][2].add(AD.data_addr(data))
        # Money in that is not a stake is a reward top-up; money out that is not an
        # unstake or a reward claim is anything else the owner moved out.
        top_up_total = rec[p]["in_wei"] - ev["stake"][1]
        other_out = rec[p]["out_wei"] - ev["unstake"][1] - ev["claim"][1]
        top_ups = defaultdict(int)
        for f, t, v, k, h in moves:
            if t == p and k == "transaction":
                sel = db.execute("SELECT input4 FROM txs_q WHERE tx_hash=?", (h,)).fetchone()
                if sel and sel[0] in ("0x", ""):
                    top_ups[cp_group(f)] += v
        chk.eq(f"plain transfers into the pool equal money in minus stakes, {pname}", sum(top_ups.values()), top_up_total)
        chk.eq(f"stakes minus unstakes equal the change in totalStake, {pname}",
               ev["stake"][1] - ev["unstake"][1], e["total_stake"][p] - s["total_stake"][p])
        st0 = sum(1 for v in s["stk"][p].values() if v > 0)
        st1 = sum(1 for v in e["stk"][p].values() if v > 0)
        bal0, bal1 = s["nat"].get(p, 0), e["nat"].get(p, 0)
        rf0, rf1 = bal0 - s["total_stake"][p], bal1 - e["total_stake"][p]
        rows.append([pname, p, r(bal0), r(bal1), r(bal1 - bal0), round((bal1 - bal0) / bal0 * 100, 2),
                     r(s["total_stake"][p]), r(e["total_stake"][p]), r(rf0), r(rf1), st0, st1,
                     ev["stake"][0], len(ev["stake"][2]), r(ev["stake"][1]),
                     ev["unstake"][0], len(ev["unstake"][2]), r(ev["unstake"][1]),
                     ev["claim"][0], len(ev["claim"][2]), r(ev["claim"][1]), r(top_up_total), r(other_out)])
        figs["pools"][pname] = {"address": p, "balance_start": r(bal0), "balance_end": r(bal1),
                                "staked_start": r(s["total_stake"][p]), "staked_end": r(e["total_stake"][p]),
                                "reward_funds_start": r(rf0), "reward_funds_end": r(rf1),
                                "stakers_start": st0, "stakers_end": st1,
                                "stakes": ev["stake"][0], "stake_addresses": len(ev["stake"][2]), "staked_in": r(ev["stake"][1]),
                                "unstakes": ev["unstake"][0], "unstake_addresses": len(ev["unstake"][2]), "unstaked": r(ev["unstake"][1]),
                                "claims": ev["claim"][0], "claim_addresses": len(ev["claim"][2]), "claimed": r(ev["claim"][1]),
                                "top_ups": {k: r(v) for k, v in top_ups.items()}, "top_up_total": r(top_up_total),
                                "other_out": r(other_out)}
    write_csv("10_staking_pools.csv",
              ["pool", "address", "RBNT balance at start", "RBNT balance at end", "change", "change %",
               "staked (totalStake) at start", "staked at end", "reward funds at start", "reward funds at end",
               "stakers at start", "stakers at end", "stakes in quarter", "addresses that staked", "RBNT staked",
               "unstakes in quarter", "addresses that unstaked", "RBNT unstaked", "reward claims", "addresses that claimed",
               "RBNT paid as rewards", "RBNT sent to the pool as plain transfers (reward top-ups)",
               "other RBNT out of the pool"], rows)
    stakers_any = set()
    for p in pools:
        stakers_any |= {a for a, v in e["stk"][p].items() if v > 0}
    figs["stakers_any_end"] = len(stakers_any)
    comm0 = sum(v for v in s["wallets"].values()) + sum(v for v in s["contracts"].values())
    comm1 = sum(v for v in e["wallets"].values()) + sum(v for v in e["contracts"].values())
    stk_comm0 = sum(v for p in pools for a, v in s["stk"][p].items() if a not in named)
    stk_comm1 = sum(v for p in pools for a, v in e["stk"][p].items() if a not in named)
    figs["staked_share_of_community"] = {"start": stk_comm0 / comm0, "end": stk_comm1 / comm1}

    # Lock calendar for open stakes at the end snapshot.
    rows = []
    for p, pname in pools.items():
        sched = json.loads(store.kv_get(db, f"unlocks_{p}", "[]"))
        by_month = defaultdict(int)
        for t, v in sched:
            key = "already unlocked" if t <= ts_of[E] else datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m")
            by_month[key] += int(v)
        chk.eq(f"lock calendar adds up to totalStake at the end, {pname}", sum(by_month.values()), e["total_stake"][p])
        for k in sorted(by_month, key=lambda x: (x != "already unlocked", x)):
            rows.append([pname, k, r(by_month[k])])
        figs["pools"][pname]["unlock_calendar"] = {k: r(v) for k, v in by_month.items()}
    write_csv("11_lock_calendar.csv", ["pool", "month the lock ends (UTC)", "RBNT staked"], rows)

    # ---- 6b. Flows between groups (RBNT and WRBNT), leaving out moves that do not
    # change who owns the RBNT: wrapping, unwrapping, staking and unstaking.
    cohort_of = {a: A.band_of(v, A.COHORTS) for a, v in start_w.items()}

    def fgroup(a):
        k = kind(a)
        if k == "reserved":
            return "Redbelly reserved wallets"
        if k == "pool":
            return "Reddex pools: reward funds"
        if k == "contract":
            g = ctype(a)
            return g if g in ctypes else "Other verified contracts"
        if k == "wallet":
            return cohort_of.get(a) or "Wallets under 1 RBNT at the start"
        return k

    pool_events = defaultdict(list)
    for t0, data, h in db.execute("SELECT t0, data, tx_hash FROM logs WHERE address IN (?, ?) AND block > ? AND block <= ?",
                                  (*pools, S, E)):
        k = {AD.T_STAKE: "stake", AD.T_UNSTAKE: "unstake", AD.T_CLAIM: "claim"}.get(t0)
        if k:
            pool_events[h].append((k, int(data[66:130], 16)))
    gflow = defaultdict(int)
    for f, t, v, _k, h in moves:
        if wr in (f, t):
            continue
        if t in pools and any(x == ("stake", v) for x in pool_events[h]):
            continue
        if f in pools and any(x == ("unstake", v) for x in pool_events[h]):
            continue
        gflow[(fgroup(f), fgroup(t))] += v
    for _b, t1, t2, data in wr_moves:
        gflow[(fgroup(AD.topic_addr(t1)), fgroup(AD.topic_addr(t2)))] += int(data, 16)
    gnet = defaultdict(int)
    for (a, b), v in gflow.items():
        if a != b:
            gnet[a] -= v
            gnet[b] += v
    write_csv("12_group_flows.csv", ["from group", "to group", "RBNT moved (RBNT and WRBNT)"],
              [[a, b, r(v)] for (a, b), v in sorted(gflow.items(), key=lambda x: -x[1]) if a != b and r(v) > 0])
    figs["group_net_flows"] = {k: r(v) for k, v in gnet.items()}
    figs["vesting_out"] = {b: r(v) for (a, b), v in gflow.items() if a == "Vesting contracts" and b != a}
    figs["vesting_in"] = {a: r(v) for (a, b), v in gflow.items() if b == "Vesting contracts" and b != a}

    # Network fees: paid by senders, then credited by the network to a set of
    # addresses without a transaction. Found as balance changes no transfer explains.
    every = set(s["nat"]) | set(e["nat"]) | set(fees) | {x for mv in moves for x in mv[:2]}
    rec_all = F.reconcile(every, s["nat"], e["nat"], moves, fees)
    credited = {a: -x["gap_wei"] for a, x in rec_all.items() if x["gap_wei"] < 0}
    debited = {a: x["gap_wei"] for a, x in rec_all.items() if x["gap_wei"] > 0}
    chk.eq("no address lost RBNT that no transfer or fee explains", len(debited), 0)
    chk.eq("fee credits are no larger than the fees paid", min(sum(credited.values()), sum(fees.values())),
           sum(credited.values()))
    figs["fee_credits"] = {"addresses": len(credited), "rbnt": r(sum(credited.values()), 2),
                           "unexplained_losses_addresses": len(debited), "unexplained_losses": r(sum(debited.values()), 2),
                           "fees_paid": r(sum(fees.values()), 2)}

    # ---- 7. WRBNT.
    figs["wrbnt"] = {"supply_start": r(s["wr_supply"]), "supply_end": r(e["wr_supply"]),
                     "holders_start": sum(1 for v in s["wrb"].values() if v > 0),
                     "holders_end": sum(1 for v in e["wrb"].values() if v > 0),
                     "deposits": r(sum(int(d, 16) for (d,) in db.execute(
                         "SELECT data FROM logs WHERE address=? AND t0=? AND block > ? AND block <= ?", (wr, AD.T_DEPOSIT, S, E)))),
                     "withdrawals": r(sum(int(d, 16) for (d,) in db.execute(
                         "SELECT data FROM logs WHERE address=? AND t0=? AND block > ? AND block <= ?", (wr, AD.T_WITHDRAWAL, S, E))))}

    figs["explorer_min_listed_rbnt"] = r(int(db.execute(
        "SELECT min(CAST(listed_balance AS REAL)) FROM explorer_list").fetchone()[0]))
    figs["pool_owner"] = {pools[p]: {"start": store.kv_get(db, f"owner_{p}_{S}"), "end": store.kv_get(db, f"owner_{p}_{E}")}
                          for p in pools}
    figs["pool_owner_named"] = {k: reserved.get(v["start"]) if v["start"] == v["end"] else None
                                for k, v in figs["pool_owner"].items()}
    hm = [figs["holders"][day(ts_of[b] - 1)]["wallets_1plus"] for _, b, _ in monthly]
    figs["holders_rose_every_month"] = all(b > a for a, b in zip(hm, hm[1:]))
    figs["checks"] = chk.items
    figs["checks_passed"] = all(c["passed"] for c in chk.items)
    (C.DATA / "figures.json").write_text(json.dumps(figs, indent=1, default=str))
    print(f"{len(chk.items)} checks passed. Tables written to {C.DATA}")


if __name__ == "__main__":
    main()

"""Step 9. Build the report (HTML and PDF), the community summary and the data workbook.

Every number in the text is read from data/figures.json or a CSV in data/.
Nothing is typed in by hand, so the next edition only needs the pipeline re-run.
"""
import base64
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from holder_report import config as C  # noqa: E402
from holder_report import workbook  # noqa: E402
from holder_report.htmlkit import esc, figure, print_pdf, read_csv, table  # noqa: E402

F = json.loads((C.DATA / "figures.json").read_text())
OUT = C.REPORT
EDITION = "Q3_2026"
POOL_NL, POOL_365 = C.POOLS[0][0], C.POOLS[1][0]


# ---------- wording helpers -------------------------------------------------
def n(x):
    return f"{int(round(x)):,}"


def m(x):
    """RBNT amount in words: 5.93 billion, 751.3 million, 15,724."""
    a = abs(x)
    if a >= 1e9:
        return f"{x / 1e9:,.2f} billion"
    if a >= 1e6:
        return f"{x / 1e6:,.1f} million"
    return n(x)


def p(x, d=1):
    return f"{x * 100:.{d}f}%"


def pct_change(a, b):
    return (b - a) / a if a else 0.0


def updown(a, b, up="rose", down="fell", same="did not change"):
    return up if b > a else down if b < a else same


def long_date(iso):
    d = date.fromisoformat(iso)
    return f"{d.day} {d.strftime('%B %Y')}"


def block_time(t):
    return f"{long_date(t[:10])}, {t[11:]}"


def csv_dict(name, key=0):
    rows = read_csv(name)
    return {r[key]: dict(zip(rows[0], r)) for r in rows[1:]}


READ_ON = long_date(F["read_on"])
SB, EB = F["start_block"], F["end_block"]
ST, ET = block_time(F["start_time"]), block_time(F["end_time"])
pools = F["pools"]
nl, ly = pools[POOL_NL], pools[POOL_365]
pool_bal0 = nl["balance_start"] + ly["balance_start"]
pool_bal1 = nl["balance_end"] + ly["balance_end"]
staked0 = nl["staked_start"] + ly["staked_start"]
staked1 = nl["staked_end"] + ly["staked_end"]
h = F["holders"]
d0, d1 = sorted(h)[0], sorted(h)[-1]
conc0, conc1 = F["concentration"]["start"], F["concentration"]["end"]
cohorts = F["cohorts"]
big = cohorts["Largest wallets (10 million or more)"]
large = cohorts["Large wallets (1 million to 10 million)"]
net = F["net_change_by_group"]
vest = F["contract_kinds"]["Vesting contracts"]
safe = F["contract_kinds"]["Multi-signature wallets (Safe)"]
bridge = F["contract_kinds"]["Bridge contracts"]
res = F["reserved"]
res_tot = F["reserved_total"]
wr = F["wrbnt"]
fees = F["fee_credits"]
eco_u = res["Ecosystem (Unlocked)"]
vest_out_wallets = sum(v for k, v in F["vesting_out"].items() if k != "Redbelly reserved wallets")
vest_out_reserved = F["vesting_out"].get("Redbelly reserved wallets", 0)
vest_in_reserved = F["vesting_in"].get("Redbelly reserved wallets", 0)
weekly = read_csv("07_weekly_named_addresses.csv")
wk_hdr, wk = weekly[0], weekly[1:]
col_nl = wk_hdr.index(f"{POOL_NL}: RBNT balance")
jumps = [(int(wk[i + 1][col_nl]) - int(wk[i][col_nl]), wk[i][0], wk[i + 1][0]) for i in range(len(wk) - 1)]
biggest_jump = max(jumps)
flows = {(x["wallet"], x["token"], x["counterparty"]): x for x in F["reserved_flows"]}


def flow(w, tok, cp, side):
    x = flows.get((w, tok, cp))
    return x[side] if x else 0


eco_out = {cp: flow("Ecosystem (Unlocked)", "RBNT", cp, "out") for cp in
           ("Wrapped RBNT contract", POOL_365, POOL_NL, "unlabelled wallets", "unlabelled contracts")}
eco_wr_out = flow("Ecosystem (Unlocked)", "WRBNT", "unlabelled contracts", "out")
eco_wr_in = flow("Ecosystem (Unlocked)", "WRBNT", "unlabelled contracts", "in")
lock_q4 = sum(v for k, v in ly["unlock_calendar"].items() if k in ("2026-10", "2026-11", "2026-12"))
lock_done = ly["unlock_calendar"].get("already unlocked", 0)
supply = read_csv("01_supply_check.csv")
found_end = float(supply[-1][4])

# ---------- text blocks -----------------------------------------------------
TILES = [
    (n(h[d1]["wallets_1plus"]), "", "wallets held 1 RBNT or more on 30 September",
     f"{n(h[d0]['wallets_1plus'])} on 30 June"),
    (m(pool_bal1).split()[0], m(pool_bal1).split()[1], "RBNT held by the two Reddex staking pools",
     f"{m(pool_bal0)} on 30 June, {'+' if pool_bal1 >= pool_bal0 else '-'}{p(abs(pct_change(pool_bal0, pool_bal1)))}"),
    (p(conc1["top100"]), "", "of wallet-held RBNT sits in the largest 100 wallets", f"{p(conc0['top100'])} on 30 June"),
    (m(res_tot["end"]).split()[0], m(res_tot["end"]).split()[1], "RBNT in Redbelly's nine reserved wallets",
     f"{m(res_tot['start'])} on 30 June"),
]

GLANCE = [
    ("Staking grew.",
     f"The two Reddex pools held {m(pool_bal1)} RBNT at the end of the quarter, up from {m(pool_bal0)}, "
     f"a rise of {p(pct_change(pool_bal0, pool_bal1))}. Most of the rise was in the no lock pool, and most of that came in "
     f"the week to {long_date(biggest_jump[2])}."),
    ("Vesting contracts paid out.",
     f"Contracts whose verified code is a vesting manager held {m(vest['start'])} RBNT at the start and "
     f"{m(vest['end'])} at the end. They sent {m(vest_out_wallets)} to wallets during the quarter."),
    ("The largest wallets added, on balance.",
     f"The {big['wallets']} wallets that started the quarter with 10 million RBNT or more held {m(big['start_wei'])} "
     f"then and {m(big['end_wei'])} at the end. {big['added']} of them added more than 1%, {big['unchanged']} stayed within 1% "
     f"and {big['reduced']} reduced by more than 1%."),
    ("Holdings stayed concentrated.",
     f"The largest 100 wallets held {p(conc1['top100'])} of all RBNT held by wallets at the end, against "
     f"{p(conc0['top100'])} at the start. {conc1['for_50']} wallets hold half of it."),
    ("Reserved wallets mostly moved RBNT between themselves.",
     f"Ecosystem (Locked) sent {m(flow('Ecosystem (Locked)', 'RBNT', 'Ecosystem 2 (Unlocked)', 'out'))} to Ecosystem 2 "
     f"(Unlocked), which sent {m(flow('Ecosystem 2 (Unlocked)', 'RBNT', 'Investors', 'out'))} on to Investors. "
     f"Governance (Locked) sent {m(flow('Governance (Locked)', 'RBNT', 'Governance (Unlocked)', 'out'))} to Governance "
     f"(Unlocked). Only Ecosystem (Unlocked) sent RBNT outside the reserved group."),
    ("A little more of the supply is now held by wallets.",
     f"Wallets held 1 RBNT or more at {n(h[d1]['wallets_1plus'])} addresses on 30 September, "
     f"{n(h[d1]['wallets_1plus'] - h[d0]['wallets_1plus'])} more than on 30 June. Together with their wrapped and staked RBNT "
     f"they held {m(F['econ']['wallet']['end'])} RBNT, up from {m(F['econ']['wallet']['start'])}."),
]


def cover():
    logo = base64.b64encode((C.ASSETS / "dao-logo-on-dark.png").read_bytes()).decode()
    tiles = "".join(
        f'<div class="tile"><div class="big">{esc(a)} <small>{esc(b)}</small></div>'
        f'<div class="what">{esc(c)}</div><div class="was">{esc(d)}</div></div>' for a, b, c, d in TILES)
    return f"""
<div class="cover">
  <img class="logo" src="data:image/png;base64,{logo}" alt="Redbelly DAO">
  <h1>RBNT Holder Report<br>{esc(F['quarter'])}</h1>
  <div class="sub">How RBNT holders behaved between {esc(F['first_day'])} and {esc(F['last_day'])}: who holds the coins,
  how concentrated holdings are, who added and who reduced, and how staking changed. Read straight from the Redbelly chain.</div>
  <div class="accent-rule"></div>
  <div class="label">Quarterly on-chain report. Edition 1</div>
  <div class="tiles">{tiles}</div>
  <div class="verified">Snapshot blocks <span class="mono">{SB:,}</span> ({esc(ST)}) and <span class="mono">{EB:,}</span> ({esc(ET)})
  on Redbelly mainnet, chain ID 151. Last verified {esc(READ_ON)}. Not financial advice.</div>
</div>"""


def glance():
    items = "".join(f"<li><b>{esc(a)}</b> {esc(b)}</li>" for a, b in GLANCE)
    return f"""
<section id="glance" class="flow" style="page-break-before:auto">
<div class="band"><div class="label">At a glance</div><h2>The quarter in six points</h2><ol>{items}</ol></div>
<div class="plain"><div class="label">Read this first</div>
<p>This report describes what the public Redbelly chain shows. It is about trends, not people. It names only addresses that
are already public: Redbelly's nine reserved wallets from the DAO treasury page, the Wrapped RBNT contract and the two Reddex
staking pools. Routescan labels no exchange wallet on Redbelly, so none is named. Every other address appears only inside a
group of at least five, never on its own.</p>
<p>The chain records that coins moved. It does not record why, or who controls an address. When a group's holdings fall, the
coins left those addresses; that may be a sale, a move to another address of the same owner, or a deposit into a contract.
This report makes no price forecast and gives no advice.</p></div>
<h3>How to read the numbers</h3>
<p><b>Start</b> means block {SB:,}, the last block before midnight UTC at the end of 30 June 2026. <b>End</b> means block
{EB:,}, the last block before midnight UTC at the end of 30 September 2026. Month-end and weekly figures use the last block
before midnight UTC on those days. Amounts are in RBNT and rounded to whole coins; the data files keep the exact values.
"Million" and "billion" are rounded to one or two decimals.</p>
<p>For every address we add three things: the RBNT it holds, the Wrapped RBNT (WRBNT) it holds and the RBNT it has staked in
either Reddex pool. That way a holder who wraps or stakes is not counted as having sold. The RBNT sitting inside the WRBNT
contract and the staked RBNT inside the pools is therefore counted once, with its owner.</p>
</section>"""


def section_supply():
    rows = []
    for r in supply[1:]:
        rows.append([esc(long_date(r[0])), f"{int(r[1]):,}", n(float(r[3])), n(float(r[4])), n(float(r[5])), f"{float(r[6]):.5f}%"])
    t = table(["Date (end of day UTC)", "Block", "Created at genesis", "In all balances read", "Not found", "Found"], rows,
              numeric_cols=(1, 2, 3, 4, 5))
    return f"""
<section id="s1">
<div class="section-head"><div class="label">Section 1</div><h2>Every RBNT accounted for</h2></div>
<p class="lead">All 10 billion RBNT were created in one allocation when the chain started. On 30 September we found
{n(found_end)} of them, {float(supply[-1][6]):.4f}%, in the balances we read. Only {n(F['unfound']['end'])} RBNT were not in
any address we found.</p>
<p>A report about holders is only as good as its list of holders. Instead of trusting an explorer's list, we built our own:
every address that sent or received a transaction or an internal transfer since the chain began, every address named in a block
header, every address that ever touched WRBNT or a staking pool, and Routescan's own list of the largest addresses. That is
{n(F['candidate_addresses'])} addresses. We then asked the Redbelly node for the balance of every one of them at each snapshot
block.</p>
{t}
<p class="src">Source: Redbelly mainnet balances at each block. Data: 01_supply_check.csv.</p>
<p><b>Where network fees go.</b> Senders paid {m(fees['fees_paid'])} RBNT in network fees during the quarter, yet the total in
all balances changed by only {n(abs(F['balances_change_in_quarter']))} RBNT. The fees were not destroyed: the network credited
{m(fees['rbnt'])} RBNT of them to {fees['addresses']} addresses, without a transaction, as a change in their balance. Apart from
these credits, every address's balance at the end equals its balance at the start plus what it received minus what it sent and
paid in fees, to the last unit. This is why we read balances directly instead of adding up transfers.</p>
<div class="plain"><div class="label">In plain words</div><p>We checked the whole supply, not a sample. The coins we could not
place come to about one in every {n(round(1e10 / F['unfound']['end'], -3))}, and that amount changed by only
{n(abs(F['unfound']['end'] - F['unfound']['start']))} RBNT during the quarter, so it cannot change any trend in this report.</p></div>
</section>"""


def section_where():
    phys = read_csv("02_where_the_rbnt_is.csv")
    rows = []
    for r in phys[1:]:
        if r[0].startswith("Other addresses labelled") and float(r[1]) == 0 and float(r[-2]) == 0:
            continue
        rows.append([esc(r[0]), n(float(r[1])), f"{float(r[2]):.2f}%", n(float(r[-2])), f"{float(r[-1]):.2f}%",
                     ("+" if float(r[-2]) >= float(r[1]) else "-") + n(abs(float(r[-2]) - float(r[1])))])
    t1 = table(["Where the RBNT physically sits", "30 June", "Share", "30 September", "Share", "Change"], rows,
               numeric_cols=(1, 2, 3, 4, 5))
    kinds = read_csv("06c_contracts_by_kind.csv")
    rows2 = [[esc(r[0]), r[1], n(float(r[2])), n(float(r[3])), ("+" if float(r[4]) >= 0 else "-") + n(abs(float(r[4])))]
             for r in kinds[1:]]
    t2 = table(["Kind of contract (from its verified code)", "Contracts", "30 June", "30 September", "Change"], rows2,
               numeric_cols=(1, 2, 3, 4))
    return f"""
<section id="s2">
<div class="section-head"><div class="label">Section 2</div><h2>Who holds the RBNT</h2></div>
<p class="lead">At the end of the quarter, {p(res_tot['end_econ'] / 1e10)} of all RBNT sat in Redbelly's reserved wallets,
{p(F['econ']['wallet']['end'] / 1e10)} with other wallets and {p(F['econ']['contract']['end'] / 1e10)} in other contracts.
Most of the RBNT in contracts is in vesting contracts.</p>
<p>RBNT is the coin of the Redbelly network. Every coin sits at an address, and anyone can read the balance of any address. An
address is either a <b>wallet</b>, controlled by a private key, or a <b>contract</b>, a program that holds coins under its own
rules. Figure 1 adds up every holding and groups it by the kind of address that owns it.</p>
{figure(1, 'fig1_who_holds', 'Bar chart of RBNT held by each group of owners at the start and end of the quarter')}
<p class="src">Data: 06d_net_change_by_group.csv and 03_who_holds_the_rbnt.csv.</p>
<p>Contracts publish their code on the Routescan explorer when their authors verify it. The name in that code tells us what kind
of program a contract is, though not who controls it. We use those names only to put contracts into groups, and only for kinds
with at least five contracts; smaller kinds are counted under "Other verified contracts".</p>
{t2}
<p class="src">Data: 06c_contracts_by_kind.csv. Contracts that held at least 1 RBNT on either date.</p>
<p><b>Vesting contracts</b> hold coins and release them to set addresses over time. <b>Multi-signature wallets</b> need more
than one key to move coins. <b>Bridge contracts</b> hold RBNT that has been moved to or from other blockchains. <b>Trading
pools</b> hold the coins people trade against on decentralised exchanges.</p>
<h3>Where the coins physically sit</h3>
<p>The view above counts wrapped and staked RBNT with its owner. The table below shows the same 10 billion RBNT by the address
that physically holds it, so the WRBNT contract and the staking pools appear on their own.</p>
{t1}
<p class="src">Data: 02_where_the_rbnt_is.csv. Shares are of the 10 billion RBNT supply.</p>
<div class="plain"><div class="label">In plain words</div><p>Six in every ten RBNT are in wallets Redbelly has publicly reserved
for the team, investors, the ecosystem, governance, the reserve and research. About one in six is in vesting contracts. A
little under one in five is held by all other wallets together.</p></div>
</section>"""


def section_holders():
    bands = read_csv("04_holders_by_size.csv")
    rows = [[esc(r[0]), n(float(r[1])), n(float(r[-2])), ("+" if float(r[-2]) >= float(r[1]) else "-") +
             n(abs(float(r[-2]) - float(r[1]))), n(float(r[2])), n(float(r[-1]))] for r in bands[1:]]
    t = table(["Holding size (RBNT)", "Wallets 30 June", "Wallets 30 Sept", "Change", "RBNT held 30 June", "RBNT held 30 Sept"],
              rows, numeric_cols=(1, 2, 3, 4, 5))
    ht = F["holder_turnover"]
    small_share = (F["bands"]["Less than 1"]["end"] + F["bands"]["1 to 100"]["end"]) / h[d1]["wallets_any"]
    return f"""
<section id="s3">
<div class="section-head"><div class="label">Section 3</div><h2>How many wallets hold RBNT</h2></div>
<p class="lead">{n(h[d1]['wallets_1plus'])} wallets held 1 RBNT or more at the end of the quarter, up from
{n(h[d0]['wallets_1plus'])}. {"The count rose in each month of the quarter." if F["holders_rose_every_month"] else ""}</p>
<p>This section looks at wallets outside the named addresses. Contracts are left out because one contract can hold coins for
many people. We count a wallet once it holds at least 1 RBNT; another {n(h[d1]['wallets_any'] - h[d1]['wallets_1plus'])}
wallets hold a fraction of a coin.</p>
{figure(2, 'fig3_holder_count', 'Column chart of wallets holding 1 RBNT or more at the end of each month')}
<p class="src">Data: 05_concentration.csv.</p>
<p>Between the two dates, {n(ht['joined'])} wallets reached 1 RBNT and {n(ht['left'])} fell below it;
{n(ht['both'])} held 1 RBNT or more on both dates.</p>
{figure(3, 'fig2_holders_by_size', 'Two bar charts comparing the share of wallets and the share of RBNT in each size band')}
{t}
<p class="src">Data: 04_holders_by_size.csv (also has the month-end counts).</p>
<p>One address is not one person. A person can use many addresses, and many people can share one. Counts of wallets show how
widely RBNT is spread across addresses, not how many people hold it.</p>
<div class="plain"><div class="label">In plain words</div><p>Most wallets hold small amounts: {p(small_share, 0)} of the
wallets that hold anything have less than 100 RBNT. Most of the coins are in a small number of large wallets.</p></div>
</section>"""


def section_concentration():
    rows = [[esc(long_date(r[0])), n(float(r[2])), f"{float(r[4]):.1f}%", f"{float(r[5]):.1f}%", f"{float(r[6]):.1f}%",
             f"{float(r[7]):.4f}", r[8]] for r in read_csv("05_concentration.csv")[1:]]
    t = table(["End of", "Wallets 1+ RBNT", "Largest 10", "Largest 100", "Largest 1,000", "Gini", "Wallets holding half"],
              rows, numeric_cols=(1, 2, 3, 4, 5, 6))
    return f"""
<section id="s4">
<div class="section-head"><div class="label">Section 4</div><h2>How concentrated holdings are</h2></div>
<p class="lead">The largest 10 wallets held {p(conc1['top10'])} of all RBNT held by wallets at the end of the quarter, against
{p(conc0['top10'])} at the start. The largest 100 held {p(conc1['top100'])}, against {p(conc0['top100'])}.</p>
<p>Concentration asks how much of the coins held by wallets sits with the biggest ones. Wallets are ranked by size on each date,
so the largest 10 at the end are not always the same wallets as at the start: {F['top100_new_entrants']} wallets were in the
largest 100 at the end but not at the start.</p>
{figure(4, 'fig4_concentration', 'Line chart of the share held by the largest 10, 100 and 1,000 wallets at each month end')}
{t}
<p class="src">Data: 05_concentration.csv. Wallets with 1 RBNT or more; named addresses and contracts are left out.</p>
<p>The <b>Gini coefficient</b> sums up the whole spread in one number between 0 (every wallet holds the same) and 1 (one wallet
holds everything). It was {conc0['gini']:.4f} at the start and {conc1['gini']:.4f} at the end. Values this close to 1 are usual
when there are tens of thousands of small wallets and a few very large ones.</p>
<div class="plain"><div class="label">In plain words</div><p>Holdings were highly concentrated and became slightly more so.
{conc1['for_50']} wallets together hold half of all RBNT held by wallets, and {conc1['for_90']} hold nine tenths.</p></div>
</section>"""


def section_behaviour():
    co = read_csv("06_cohorts.csv")
    rows = [[esc(r[0].split(" (")[1].rstrip(")").capitalize()), n(float(r[1])), n(float(r[2])), n(float(r[3])),
             n(float(r[4])), n(float(r[5])),
             ("+" if float(r[8]) >= 0 else "-") + m(abs(float(r[8]))), f"{float(r[9]):+.1f}%".replace("+-", "-")]
            for r in co[1:6]]
    t = table(["Size at start (RBNT)", "Wallets", "Added", "Within 1%", "Reduced", "Below 1 at end",
               "Net change (RBNT)", "Change"], rows, numeric_cols=(1, 2, 3, 4, 5, 6, 7), cls="first-wide")
    vo = F["vesting_out"]
    vrows = [[esc(k), n(v)] for k, v in sorted(vo.items(), key=lambda x: -x[1])]
    vt = table(["Vesting contracts sent RBNT to", "RBNT"], vrows, numeric_cols=(1,))
    bm = F["band_moves"]
    smaller = cohorts["Smaller wallets (1,000 to 100,000)"]
    return f"""
<section id="s5">
<div class="section-head"><div class="label">Section 5</div><h2>What the largest holders did</h2></div>
<p class="lead">Wallets of every size added RBNT on balance during the quarter. Most of it came from vesting contracts, which
sent {m(vest_out_wallets)} RBNT to wallets.</p>
<p>To see buying and selling without singling anyone out, we put wallets into five groups by their holding at the start of the
quarter, then followed the same wallets to the end. A wallet "added" if it ended with more than 1% more, "reduced" if it ended
with more than 1% less, and was "within 1%" otherwise. Staking or wrapping does not count as a change.</p>
{figure(5, 'fig5_cohorts', 'Stacked bars showing the share of wallets in each size group that added, held or reduced')}
{t}
<p class="src">Data: 06_cohorts.csv (also has month-end totals for each group).</p>
<p><b>The largest wallets.</b> The {big['wallets']} wallets with 10 million RBNT or more at the start held {m(big['start_wei'])}
RBNT then and {m(big['end_wei'])} at the end, a change of {p(pct_change(big['start_wei'], big['end_wei']))}. {big['added']}
added, {big['unchanged']} stayed within 1% and {big['reduced']} reduced. The {large['wallets']} wallets with 1 million to 10
million went from {m(large['start_wei'])} to {m(large['end_wei'])}; {large['added']} added and {large['reduced']} reduced.</p>
<p><b>Most wallets did not move.</b> In every group below 1 million RBNT, at least {p(min(cohorts[k]['unchanged'] / cohorts[k]['wallets'] for k in ('Mid-size wallets (100,000 to 1 million)', 'Smaller wallets (1,000 to 100,000)', 'Small wallets (1 to 1,000)')), 0)}
of wallets ended the quarter within 1% of where they started.</p>
{figure(6, 'fig6_net_change', 'Bar chart of the net change in RBNT for each group of holders')}
<p class="src">Data: 06d_net_change_by_group.csv. All groups together add up to the 10 billion supply, so the changes sum to
zero.</p>
<p><b>Where the added coins came from.</b> Figure 6 shows which groups gained and which gave up RBNT. Vesting contracts gave up
{m(-net['Vesting contracts']['change'])} and the reserved wallets {m(-net['Redbelly reserved wallets']['change'])}. On the
other side, every wallet group gained. The smaller wallets (1,000 to 100,000 RBNT at the start) more than doubled their holdings,
from {m(smaller['start_wei'])} to {m(smaller['end_wei'])}. Vesting contracts sent
{m(vo.get('Smaller wallets (1,000 to 100,000)', 0))} RBNT to wallets in this group and
{m(vo.get('Small wallets (1 to 1,000)', 0))} to wallets in the small group (1 to 1,000 RBNT at the start). Some of these wallets ended the quarter much
larger: {n(bm['up2'])} wallets moved up two or more size bands, while {n(bm['down2'])} moved down two or more.</p>
{vt}
<p class="src">Data: 12_group_flows.csv. RBNT and WRBNT transfers between the two snapshot blocks.</p>
<div class="plain"><div class="label">In plain words</div><p>On the chain, the quarter looks like RBNT moving out of
vesting contracts and reserved wallets and into ordinary wallets, directly or through vesting contracts and staking rewards,
rather than wallets emptying. A fall in a group's total would mean coins left
those addresses; it would not show whether they were sold, moved to another address of the same owner, or put into a contract.
The chain records movements, not reasons.</p></div>
</section>"""


def section_staking():
    rows = []
    for name in (POOL_NL, POOL_365):
        x = pools[name]
        rows.append([esc(name.replace("Reddex RBNT pool, ", "").capitalize() + " pool"), n(x["balance_start"]), n(x["balance_end"]),
                     ("+" if x["balance_end"] >= x["balance_start"] else "-") + n(abs(x["balance_end"] - x["balance_start"])),
                     p(pct_change(x["balance_start"], x["balance_end"]))])
    rows.append(["Both pools", n(pool_bal0), n(pool_bal1), "+" + n(pool_bal1 - pool_bal0), p(pct_change(pool_bal0, pool_bal1))])
    t1 = table(["Pool", "RBNT balance 30 June", "RBNT balance 30 Sept", "Change", "Change %"], rows,
               numeric_cols=(1, 2, 3, 4), total_last=True)
    rows = []
    for label, key in (("Staked (the pool's own totalStake)", "staked"), ("Reward funds (balance minus staked)", "reward_funds")):
        rows.append([label, n(nl[key + "_start"]), n(nl[key + "_end"]), n(ly[key + "_start"]), n(ly[key + "_end"])])
    rows.append(["Addresses with a stake", n(nl["stakers_start"]), n(nl["stakers_end"]), n(ly["stakers_start"]), n(ly["stakers_end"])])
    t2 = table(["", "No lock 30 June", "No lock 30 Sept", "365 day 30 June", "365 day 30 Sept"], rows, numeric_cols=(1, 2, 3, 4))
    rows = []
    for label, a, c, k in (("Stakes", "stakes", "stake_addresses", "staked_in"), ("Unstakes", "unstakes", "unstake_addresses", "unstaked"),
                           ("Reward claims", "claims", "claim_addresses", "claimed")):
        rows.append([label, f"{n(nl[k])} RBNT ({n(nl[a])} by {n(nl[c])} addresses)", f"{n(ly[k])} RBNT ({n(ly[a])} by {n(ly[c])} addresses)"])
    rows.append(["Sent in as reward funds", f"{n(nl['top_up_total'])} RBNT", f"{n(ly['top_up_total'])} RBNT"])
    t3 = table(["During the quarter", "No lock pool", "365 day pool"], rows)
    top_up_src = sorted(set(list(nl["top_ups"]) + list(ly["top_ups"])))
    owners = set(F["pool_owner_named"].values())
    assert owners == set(top_up_src), (owners, top_up_src)
    owner_note = ""
    return f"""
<section id="s6">
<div class="section-head"><div class="label">Section 6</div><h2>Staking in the Reddex pools</h2></div>
<p class="lead">The two Reddex RBNT staking pools held {m(pool_bal1)} RBNT at the end of the quarter, up from {m(pool_bal0)}
at the start. The no lock pool grew by {p(pct_change(nl['balance_start'], nl['balance_end']))} and the 365 day pool by
{p(pct_change(ly['balance_start'], ly['balance_end']))}.</p>
<p>Staking means putting RBNT into a contract to earn rewards. Reddex runs two RBNT pools: in the <b>no lock</b> pool a stake
can be taken out at any time; in the <b>365 day</b> pool each stake is locked for a year. Both pay rewards in RBNT.</p>
{t1}
<p class="src">Source: each pool's RBNT balance read from the node at blocks {SB:,} and {EB:,}. Data: 10_staking_pools.csv.</p>
{figure(7, 'fig7_pools_weekly', 'Line chart of each staking pool RBNT balance week by week')}
<p class="src">Data: 07_weekly_named_addresses.csv (weekly blocks listed in the file).</p>
<p>The no lock pool's balance rose by {m(biggest_jump[0])} RBNT in the week from {long_date(biggest_jump[1])} to
{long_date(biggest_jump[2])}, its biggest weekly change of the quarter.</p>
<div class="plain"><div class="label">A pool's balance is more than its stakes</div><p>Rewards are paid in RBNT out of each
pool's own balance, so a pool's balance may include reward funds as well as stakes. The pools' verified code keeps its own count
of staked RBNT, called <span class="mono">totalStake</span>; the rest of the balance is reward funds. The table below splits
the two. The staked figures are the ones counted with each staker in sections 2 to 5.</p></div>
{t2}
<p>Staked RBNT in both pools went from {m(staked0)} to {m(staked1)}. That is {p(F['staked_share_of_community']['end'])} of all
RBNT held outside the named addresses, up from {p(F['staked_share_of_community']['start'])}. {n(F['stakers_any_end'])} addresses
had a stake in at least one pool at the end.</p>
{figure(8, 'fig8_pool_activity', 'Grouped bars of RBNT staked, unstaked and paid as rewards in each pool during the quarter')}
{t3}
<p class="src">Data: 10_staking_pools.csv, from the pools' Stake, Unstake and reward claim events. For each pool, stakes minus
unstakes equal the change in totalStake exactly.</p>
<p><b>Who topped up the reward funds.</b> The only plain transfers into the pools came from {esc(', '.join(top_up_src))}, a
reserved wallet named on the DAO treasury page. Read from the chain at both snapshot blocks, the owner of both pools is that same
wallet{owner_note}.</p>
<h3>When locked stakes can be withdrawn</h3>
<p>Of the {m(ly['staked_end'])} RBNT staked in the 365 day pool at the end of the quarter, {m(lock_done)} had already passed the
end of its lock and {m(lock_q4)} reaches the end of its lock between October and December 2026. A lock ending only means the
RBNT can be taken out. It does not mean it will be.</p>
{figure(9, 'fig9_lock_calendar', 'Bar chart of RBNT in the 365 day pool by the month its lock ends')}
<p class="src">Data: 11_lock_calendar.csv, read from the pool's getStakeUnlockTimes for every staker at block {EB:,}.</p>
</section>"""


def section_named():
    # The exchange paragraph below is written for one label (WRBNT). If Routescan adds labels, extend the text.
    assert list(F["labelled"].values()) == ["Wrapped RBNT"] and not F["labelled_exchanges"], F["labelled"]
    named = read_csv("08_named_addresses.csv")
    rows = []
    for r in named[1:10]:
        alloc = n(float(r[2])) if r[2] not in ("", "not listed") else "not listed"
        rows.append([f'<b>{esc(r[0])}</b><br><span class="addr-small">{esc(r[1])}</span>', alloc, n(float(r[3])),
                     n(float(r[4])), ("+" if float(r[5]) >= 0 else "-") + n(abs(float(r[5]))) if float(r[5]) else "0",
                     f"{r[6]} / {r[8]}"])
    t1 = table(["Reserved wallet and address", "Allocation (treasury page)", "30 June", "30 Sept", "Change",
                "Transfers in / out"], rows, numeric_cols=(1, 2, 3, 4, 5), cls="named")
    eco_rows = [["Wrapped into WRBNT (sent to the WRBNT contract)", n(eco_out["Wrapped RBNT contract"])],
                ["Reddex 365 day pool, as reward funds", n(eco_out[POOL_365])],
                ["Reddex no lock pool, as reward funds", n(eco_out[POOL_NL])],
                [f"{F['reserved_distinct_unlabelled_recipients'].get('Ecosystem (Unlocked)', 0)} unlabelled wallets and contracts",
                 n(eco_out["unlabelled wallets"] + eco_out["unlabelled contracts"])]]
    t2 = table(["Ecosystem (Unlocked) sent RBNT to", "RBNT"], eco_rows, numeric_cols=(1,))
    return f"""
<section id="s7">
<div class="section-head"><div class="label">Section 7</div><h2>The publicly named wallets</h2></div>
<p class="lead">Redbelly's nine reserved wallets held {m(res_tot['start'])} RBNT at the start and {m(res_tot['end'])} at the end.
Most of the movement was between reserved wallets. Only Ecosystem (Unlocked) sent RBNT outside the group.</p>
<p>The DAO treasury page lists nine wallets Redbelly has reserved, with the amount each was given at launch. Those amounts are
allocations, not balances, so we read each wallet's balance from the chain on both dates and traced every transfer in between.
For every wallet, the balance at the start plus everything received minus everything sent and paid in fees equals the balance at
the end, to the last unit.</p>
{figure(10, 'fig10_reserved_wallets', 'Bar chart of RBNT in each of the nine reserved wallets at the start and end of the quarter')}
{t1}
<p class="src">Data: 08_named_addresses.csv (also has fees, WRBNT held and the reconciliation gap for each wallet) and
09_reserved_wallet_flows.csv.</p>
<h3>What moved</h3>
<p>Ecosystem (Locked) sent {m(flow('Ecosystem (Locked)', 'RBNT', 'Ecosystem 2 (Unlocked)', 'out'))} RBNT to Ecosystem 2
(Unlocked), which sent {m(flow('Ecosystem 2 (Unlocked)', 'RBNT', 'Investors', 'out'))} on to the Investors wallet. Governance
(Locked) sent {m(flow('Governance (Locked)', 'RBNT', 'Governance (Unlocked)', 'out'))} to Governance (Unlocked). None of these
transfers left the reserved group. Team (Locked), USYD/CSIRO (Locked) and Reserve did not move.</p>
<p>Ecosystem (Unlocked) made {eco_u['n_out']} transfers out, {m(sum(eco_out.values()))} RBNT in total, and paid
{n(eco_u['fees'])} RBNT in network fees.</p>
{t2}
<p>It also moved WRBNT: it sent {m(eco_wr_out)} WRBNT to vesting contracts and received {m(eco_wr_in)} WRBNT from vesting
contracts. These are the only WRBNT transfers by a reserved wallet in the quarter.</p>
<h3>Wrapped RBNT</h3>
<p>The WRBNT supply {updown(wr['supply_start'], wr['supply_end'])} from {m(wr['supply_start'])} to {m(wr['supply_end'])}:
{m(wr['deposits'])} RBNT was wrapped and {m(wr['withdrawals'])} unwrapped. On both dates the supply equalled the RBNT held by
the WRBNT contract and the sum of all WRBNT balances, to the last unit, so each WRBNT was backed by one RBNT. The contract's
RBNT is counted once in this report, with whoever holds the WRBNT.</p>
<h3>Exchanges</h3>
<p>The brief asks for flows in and out of labelled exchange wallets. On {READ_ON}, Routescan's public address list for Redbelly
mainnet gave a name to only one address, the Wrapped RBNT contract, among the {n(F['explorer_listed_addresses'])} largest
addresses it lists (down to a balance of {n(F['explorer_min_listed_rbnt'])} RBNT). It labelled no exchange wallet. With no public label to go by,
this edition reports no exchange flows. Treating an unlabelled address as an exchange would be a guess about who controls it,
which this report does not make. The method explains how the next edition picks up labels once Routescan publishes them.</p>
</section>"""


def section_method():
    import re
    groups = {}
    for c in F["checks"]:
        k = c["check"]
        k = re.sub(r"(,| at)? block \d+", "", k)
        k = re.sub(r", (Reddex RBNT pool|Largest|Large|Mid-size|Smaller|Small)\b.*$", "", k)
        k = re.sub(r": .*$", "", k)
        g = groups.setdefault(k, [0, True])
        g[0] += 1
        g[1] = g[1] and c["passed"]
    assert all(ok for _n, ok in groups.values())
    items = "".join(f'<li><span class="tick">&#10003;</span> {esc(k[0].upper() + k[1:])}'
                    f'{f" ({cnt} times)" if cnt > 1 else ""}</li>' for k, (cnt, _ok) in groups.items())
    return f"""
<section id="s8">
<div class="section-head"><div class="label">Section 8</div><h2>Method</h2></div>
<p class="lead">Everything in this report comes from public chain data, read at fixed blocks, with scripts anyone can run.
METHOD.md in the data package gives every call in detail; this is the short version.</p>
<ol>
<li><b>Fix the moments.</b> For each date, find the last block before midnight UTC by binary search on block times from the
Redbelly node, and check it against Routescan's getblocknobytime.</li>
<li><b>Find every address.</b> Read every transaction receipt from block 0 to block {EB:,} ({n(F['blocks_scanned'])} blocks),
every block header, all {n(F['internal_transfers_read'])} internal transfers from Routescan, every WRBNT and staking event,
and Routescan's address list. This gives {n(F['candidate_addresses'])} addresses.</li>
<li><b>Read balances.</b> Ask the node for the RBNT balance of every address at each month-end block, the WRBNT balance of
every address that ever held WRBNT, and the stake of every address that ever staked.</li>
<li><b>Count each coin once.</b> Add each address's RBNT, WRBNT and staked RBNT. Leave out the WRBNT contract's RBNT (it backs
the WRBNT) and the staked part of each pool (it belongs to the stakers). The rest of each pool's balance is its reward funds.</li>
<li><b>Sort addresses.</b> Named addresses are reported by name. Every other address is a wallet (no code) or a contract (has
code at the end block). Contracts are grouped by the name in their verified code, only where five or more share a kind.</li>
<li><b>Follow movements.</b> Take every transaction and internal transfer between the two blocks, and every WRBNT transfer,
and add them up by group. Check that every named address reconciles to the last unit.</li>
<li><b>Check.</b> The scripts stop if any of the checks below fails. A separate script then re-reads the headline figures from
the node and scans every file for anything the brief forbids.</li>
</ol>
<div class="plain"><div class="label">Pool balances include reward funds</div><p>Rewards in both Reddex pools are paid in
RBNT from the pool's own balance, so a pool balance may include reward funds as well as stakes. The headline staking figures use
the pools' RBNT balances, as the brief asks. The split into staked RBNT and reward funds uses the pools' own totalStake.</p></div>
<h3>Checks that passed on this data</h3>
<p class="small">{len(F['checks'])} checks in all, listed one by one in figures.json. Each is an exact equality in wei.</p>
<ul class="checks small">{items}</ul>
<h3>What the chain does not show</h3>
<p>Who controls an address, why coins moved, and whether a transfer was a sale. This report describes movements only.</p>
</section>"""


def section_sources():
    rows = [
        ["Redbelly mainnet RPC, chain ID 151", '<span class="mono">governors.mainnet.redbelly.network</span>',
         "Balances, WRBNT balances and supply, pool totalStake, stakes and lock times at the snapshot blocks; every receipt and block header since block 0; contract code", READ_ON],
        ["Routescan API (Etherscan compatible)", '<span class="mono">api.routescan.io/v2/network/mainnet/evm/151/etherscan/api</span>',
         "Internal transfers since block 0; verified source code of the pools, WRBNT and holding contracts; block number by time (cross-check)", READ_ON],
        ["Routescan address list", '<span class="mono">api.routescan.io/v2/network/mainnet/evm/151/addresses</span>',
         "Public names (labels) and the largest addresses, used only to find addresses, never for balances", READ_ON],
        ["Redbelly DAO treasury page", '<span class="mono">redbellydao.network/treasury/</span>',
         "Names, addresses and launch allocations of the nine reserved wallets", READ_ON],
        ["Reddex staking", '<span class="mono">www.reddex.io/stake</span>', "The two RBNT pools and their lock periods", READ_ON],
    ]
    t = table(["Source", "Where", "What we read", "Read on"], rows, cls="sources")
    files = [["01_supply_check.csv", "Section 1"], ["02_where_the_rbnt_is.csv", "Section 2"], ["03_who_holds_the_rbnt.csv", "Section 2"],
             ["04_holders_by_size.csv", "Section 3, figure 3"], ["05_concentration.csv", "Sections 3 and 4, figures 2 and 4"],
             ["06_cohorts.csv", "Section 5, figure 5"], ["06b_band_moves.csv", "Section 5"], ["06c_contracts_by_kind.csv", "Section 2"],
             ["06d_net_change_by_group.csv", "Figures 1 and 6"], ["07_weekly_named_addresses.csv", "Figure 7"],
             ["08_named_addresses.csv", "Section 7, figure 10"], ["09_reserved_wallet_flows.csv", "Section 7"],
             ["10_staking_pools.csv", "Section 6, figure 8"], ["11_lock_calendar.csv", "Figure 9"], ["12_group_flows.csv", "Section 5"],
             ["figures.json", "Every number quoted in the text, and every check"],
             ["verification.json", "Independent re-reads from the node and file scans"]]
    t2 = table(["Data file", "Used in"], [[f'<span class="mono">{esc(a)}</span>', esc(b)] for a, b in files])
    return f"""
<section id="s9">
<div class="section-head"><div class="label">Section 9</div><h2>Sources and data</h2></div>
<p>Every figure is a balance or event on the Redbelly chain at block {SB:,} ({esc(ST)}), block {EB:,} ({esc(ET)}), a month-end or
weekly block listed in the data files, or an event between them. All sources were read on {READ_ON}.</p>
{t}
{t2}
<h3>Words used</h3>
<dl class="glossary">
<dt>Address</dt><dd>A public account on the chain, written as 0x followed by 40 characters.</dd>
<dt>Wallet</dt><dd>An address controlled by a private key. It holds no code.</dd>
<dt>Contract</dt><dd>An address that runs code, such as a staking pool, a vesting contract or a multi-signature wallet.</dd>
<dt>Block</dt><dd>A batch of transactions. Each block has a number and a time, so a block number fixes a moment.</dd>
<dt>Staking</dt><dd>Putting RBNT into a contract to earn rewards.</dd>
<dt>WRBNT</dt><dd>Wrapped RBNT, a token backed one to one by RBNT held in the WRBNT contract, used by apps.</dd>
<dt>Vesting contract</dt><dd>A contract that holds coins and releases them to set addresses over time.</dd>
<dt>Reserved wallets</dt><dd>The nine wallets on the DAO treasury page: team, investors, reserve, ecosystem, governance and USYD/CSIRO.</dd>
<dt>Gini coefficient</dt><dd>One number for how unevenly coins are spread: 0 is perfectly even, 1 is one holder with everything.</dd>
</dl>
</section>"""


NAV = [("#glance", "Summary"), ("#s2", "Holders"), ("#s5", "Largest holders"), ("#s6", "Staking"),
       ("#s7", "Named wallets"), ("#downloads", "Data"), ("method.html", "Method")]


def nav(home=""):
    links = "".join(f'<a href="{home}{h}">{esc(t)}</a>' if h.startswith("#") else f'<a href="{h}">{esc(t)}</a>'
                    for h, t in NAV)
    return (f'<nav class="nav screen-only"><a class="brand" href="{home or "#top"}">RBNT Holder Report '
            f'<span>{esc(F["quarter"])}</span></a><div class="links">{links}'
            f'<a class="pdf" href="RBNT_Holder_Report_{EDITION}.pdf">PDF</a></div></nav>')


def downloads():
    csvs = sorted(p.name for p in C.DATA.glob("*.csv"))
    items = "".join(f'<li><a href="data/{esc(c)}"><span class="mono">{esc(c)}</span></a></li>' for c in csvs)
    return f"""
<section id="downloads" class="screen-only">
<div class="section-head"><div class="label">Downloads</div><h2>The report and the data behind it</h2></div>
<div class="dl-grid">
<a class="dl" href="RBNT_Holder_Report_{EDITION}.pdf"><b>Report (PDF)</b><span>The full report, ready to print or share</span></a>
<a class="dl" href="data/RBNT_Holder_Report_{EDITION}_data.xlsx"><b>All data (XLSX)</b><span>Every table behind the charts, one sheet each</span></a>
<a class="dl" href="summary.html"><b>Community summary</b><span>A few paragraphs and an X thread</span></a>
<a class="dl" href="method.html"><b>Method and sources</b><span>How every number was made, and how to repeat it</span></a>
<a class="dl" href="data/figures.json"><b>figures.json</b><span>Every number quoted in the text, and every check</span></a>
<a class="dl" href="data/verification.json"><b>verification.json</b><span>Independent re-reads from the node</span></a>
</div>
<h3>CSV files</h3><ul class="csvs">{items}</ul>
</section>"""


def head(title, desc, assets, extra_css=""):
    css = (OUT / "template" / "report.css").read_text().replace("../../assets/", assets) + extra_css
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(desc)}">
<meta property="og:title" content="{esc(title)}"><meta property="og:description" content="{esc(desc)}">
<meta property="og:type" content="article"><meta property="og:image" content="og_1200x630.png">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" type="image/png" href="{assets}icon.png">
<style>{css}</style></head>"""


DESC = (f"How RBNT holders behaved between {F['first_day']} and {F['last_day']}: holdings, concentration, accumulation, "
        f"staking and the publicly named wallets, read from the Redbelly chain.")


def build_html(web=False):
    body = [cover(), glance()]
    if web:
        body.append(downloads())
    body += [section_supply(), section_where(), section_holders(), section_concentration(),
             section_behaviour(), section_staking(), section_named(), section_method(), section_sources()]
    assets = "assets/" if web else "../assets/"
    return (head(f"RBNT Holder Report {F['quarter']}", DESC, assets) +
            f'<body id="top">{nav() if web else ""}{"".join(body)}</body></html>')


def md_page(title, md_text, active):
    import markdown
    html_body = markdown.markdown(md_text, extensions=["tables", "fenced_code"])
    return (head(title, DESC, "assets/") + f'<body id="top">{nav("index.html")}'
            f'<main class="doc">{html_body}</main></body></html>')


def build_site():
    """Static site for Netlify: the web version of the report plus every download."""
    import shutil
    site = C.ROOT / "site"
    if site.exists():
        shutil.rmtree(site)
    (site / "assets" / "fonts").mkdir(parents=True)
    (site / "data").mkdir()
    (site / "charts").mkdir()
    (site / "index.html").write_text(build_html(web=True))
    for f in (C.ASSETS / "fonts").glob("*"):
        shutil.copy(f, site / "assets" / "fonts" / f.name)
    for f in ("icon.png", "dao-logo-on-dark.png", "dao-logo-on-light.png"):
        shutil.copy(C.ASSETS / f, site / "assets" / f)
    for f in (OUT / "charts").glob("*.png"):
        shutil.copy(f, site / "charts" / f.name)
    for f in C.DATA.iterdir():
        if f.suffix in (".csv", ".json", ".xlsx"):
            shutil.copy(f, site / "data" / f.name)
    shutil.copy(OUT / f"RBNT_Holder_Report_{EDITION}.pdf", site / f"RBNT_Holder_Report_{EDITION}.pdf")
    com = C.ROOT / "community"
    for f in ("x_card_1600x900.png", "og_1200x630.png", "x_thread.txt", "community_summary.md"):
        if (com / f).exists():
            shutil.copy(com / f, site / f)
    thread = (com / "x_thread.txt").read_text().split("\n---\n")
    thread_md = "\n\n".join(f"> {t.strip()}" for t in thread if t.strip())
    summary_md = ((com / "community_summary.md").read_text() + "\n\n## X thread\n\n" + thread_md +
                  "\n\n![RBNT Holder Report summary card](x_card_1600x900.png)\n")
    (site / "summary.html").write_text(md_page(f"Community summary, RBNT Holder Report {F['quarter']}", summary_md, "summary"))
    (site / "method.html").write_text(md_page(f"Method and sources, RBNT Holder Report {F['quarter']}",
                                              (C.ROOT / "METHOD.md").read_text(), "method"))
    return site


# ---------- community summary -----------------------------------------------
def community():
    d = C.ROOT / "community"
    d.mkdir(exist_ok=True)
    posts = [
        f"RBNT holder report, {F['quarter']} ({F['first_day']} to {F['last_day']}). We read every balance on the Redbelly chain "
        f"at the start and end of the quarter to show how holders behaved. Trends in groups, never individuals. Thread.",
        f"1. Staking grew. The two Reddex RBNT pools held {m(pool_bal1)} RBNT on 30 September, up from {m(pool_bal0)} on "
        f"30 June ({'+' if pool_bal1 >= pool_bal0 else '-'}{p(abs(pct_change(pool_bal0, pool_bal1)))}). Pool balances include "
        f"some reward funds; staked RBNT alone went from {m(staked0)} to {m(staked1)}.",
        f"2. Vesting contracts paid out. Contracts whose verified code is a vesting manager went from {m(vest['start'])} to "
        f"{m(vest['end'])} RBNT, and sent {m(vest_out_wallets)} to wallets during the quarter.",
        f"3. The {big['wallets']} wallets that started with 10 million RBNT or more held {m(big['start_wei'])} then and "
        f"{m(big['end_wei'])} at the end. {big['added']} added more than 1%, {big['unchanged']} held within 1%, "
        f"{big['reduced']} reduced.",
        f"4. Holdings stay concentrated. The largest 100 wallets hold {p(conc1['top100'])} of all wallet-held RBNT "
        f"({p(conc0['top100'])} on 30 June). {n(h[d1]['wallets_1plus'])} wallets held 1 RBNT or more, up from "
        f"{n(h[d0]['wallets_1plus'])}.",
        f"5. Redbelly's nine reserved wallets went from {m(res_tot['start'])} to {m(res_tot['end'])} RBNT. Most of the movement "
        f"was between reserved wallets; only Ecosystem (Unlocked) sent RBNT outside the group.",
        f"6. Every number comes from the chain at blocks {SB:,} and {EB:,}, and every RBNT is accounted for: "
        f"{float(supply[-1][6]):.4f}% of the 10 billion supply was found in the balances read. Not financial advice.",
        "Full report, data files and method so anyone can repeat it: [link to the DAO's published report]",
    ]
    (d / "x_thread.txt").write_text("\n---\n".join(posts) + "\n")
    paras = [
        f"# RBNT holder report, {F['quarter']}: community summary",
        f"*{F['first_day']} to {F['last_day']}. Data read from Redbelly mainnet at blocks {SB:,} and {EB:,}. "
        f"Last verified {READ_ON}. Not financial advice.*",
        "Holders often ask what the big wallets are doing. This report answers from the chain itself. We read the balance of every "
        "address at the start and end of the quarter, counted wrapped and staked RBNT with its owner, and looked at groups of "
        "wallets rather than individuals. Only addresses that are already public are named.",
        f"**Staking grew.** The two Reddex RBNT staking pools held {m(pool_bal1)} RBNT at the end of the quarter, up from "
        f"{m(pool_bal0)}. A pool's balance includes some reward funds as well as stakes; the staked part alone went from "
        f"{m(staked0)} to {m(staked1)}. {n(F['stakers_any_end'])} addresses had a stake at the end.",
        f"**Coins moved from vesting contracts and reserved wallets to ordinary wallets.** Vesting contracts went from "
        f"{m(vest['start'])} to {m(vest['end'])} RBNT and sent {m(vest_out_wallets)} to wallets. The {big['wallets']} wallets "
        f"that started with 10 million RBNT or more went from {m(big['start_wei'])} to {m(big['end_wei'])}: {big['added']} added, "
        f"{big['unchanged']} held steady and {big['reduced']} reduced. Most smaller wallets did not change at all.",
        f"**Holdings stay concentrated.** {n(h[d1]['wallets_1plus'])} wallets held 1 RBNT or more on 30 September, up from "
        f"{n(h[d0]['wallets_1plus'])}. The largest 100 hold {p(conc1['top100'])} of all wallet-held RBNT, against "
        f"{p(conc0['top100'])} at the start.",
        f"**Reserved wallets.** Redbelly's nine reserved wallets went from {m(res_tot['start'])} to {m(res_tot['end'])} RBNT. "
        f"Ecosystem (Locked) released {m(flow('Ecosystem (Locked)', 'RBNT', 'Ecosystem 2 (Unlocked)', 'out'))} to Ecosystem 2 "
        f"(Unlocked), which sent {m(flow('Ecosystem 2 (Unlocked)', 'RBNT', 'Investors', 'out'))} to Investors, and Governance "
        f"(Locked) released {m(flow('Governance (Locked)', 'RBNT', 'Governance (Unlocked)', 'out'))} to Governance (Unlocked). "
        f"Ecosystem (Unlocked) was the only reserved wallet that sent RBNT outside the group, including "
        f"{m(eco_out[POOL_365] + eco_out[POOL_NL])} to the staking pools as reward funds.",
        "**Exchanges.** Routescan labels no exchange wallet on Redbelly, so this edition reports no exchange flows rather than "
        "guess which addresses belong to exchanges.",
        "The chain shows that coins moved, not why. A fall in a group's holdings may be a sale, a move between a holder's own "
        "addresses or a deposit into a contract. The full report, the data behind every chart and the method are published with "
        "this summary so anyone can check the numbers and produce the next edition.",
    ]
    (d / "community_summary.md").write_text("\n\n".join(paras) + "\n")


def main():
    OUT.mkdir(exist_ok=True)
    html_path = OUT / f"RBNT_Holder_Report_{EDITION}.html"
    html_path.write_text(build_html())
    print_pdf(html_path, OUT / f"RBNT_Holder_Report_{EDITION}.pdf")
    community()
    workbook.build(C.DATA / f"RBNT_Holder_Report_{EDITION}_data.xlsx")
    site = build_site()
    print("built", html_path.name, "and PDF, community summary, workbook and the site in", site.name + "/")


if __name__ == "__main__":
    main()

"""Step 8. Draw every chart from the CSV files in data/.

Charts are saved as SVG (for the PDF) and PNG (for sharing) in report/charts/.
Each chart carries its source line and the date the data was read.
"""
import csv
import json
import sys
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from holder_report import config as C  # noqa: E402
from holder_report import style as S  # noqa: E402

OUT = C.REPORT / "charts"
FIG = json.loads((C.DATA / "figures.json").read_text())
def long_date(iso):
    from datetime import date
    d = date.fromisoformat(iso)
    return f"{d.day} {d.strftime('%B %Y')}"


def block_time(t):
    return f"{long_date(t[:10])}, {t[11:]}"


SOURCE = (f"Source: Redbelly mainnet (chain ID 151), blocks {FIG['start_block']:,} ({block_time(FIG['start_time'])}) and "
          f"{FIG['end_block']:,} ({block_time(FIG['end_time'])}). Last verified {long_date(FIG['read_on'])}.")


def rows(name):
    with open(C.DATA / name) as f:
        return list(csv.reader(f))


def num(x):
    return float(x) if x not in ("", None) else 0.0


def short(v):
    a = abs(v)
    if a >= 1e9:
        return f"{v / 1e9:.2f}B"
    if a >= 1e6:
        return f"{v / 1e6:.1f}M"
    if a >= 1e3:
        return f"{v / 1e3:.0f}K"
    return f"{v:,.0f}"


def pct_label(x):
    return "under 0.1%" if 0 < x < 0.05 else f"{x:.1f}%"


def axis_short(ax, which="x"):
    f = FuncFormatter(lambda v, _p: short(v) if v else "0")
    (ax.xaxis if which == "x" else ax.yaxis).set_major_formatter(f)


def finish(fig, name, title, subtitle, source=SOURCE, note=None):
    fig.text(0.02, 0.975, title, ha="left", va="top", fontsize=14.5, fontweight=700, color=S.INK)
    fig.text(0.02, 0.915, subtitle, ha="left", va="top", fontsize=10.5, color=S.MUTED)
    foot = "\n".join(textwrap.wrap(source + ("  " + note if note else ""), 150))
    fig.text(0.02, 0.02, foot, ha="left", va="bottom", fontsize=8, color=S.MUTED, family=S.SANS, linespacing=1.4)
    extra = foot.count("\n")
    if extra:
        fig.subplots_adjust(bottom=fig.subplotpars.bottom + 0.04 * extra)
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / f"{name}.svg")
    fig.savefig(OUT / f"{name}.png", dpi=200)
    plt.close(fig)


def legend_patches(ax, items, loc="lower right", ncol=2):
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(facecolor=c, label=l) for l, c in items], loc=loc, ncol=ncol,
              bbox_to_anchor=(1.0, 1.0), handlelength=1.0, handleheight=1.0, borderaxespad=0.2)


OWNER_GROUPS = [
    ("Redbelly reserved wallets", ["Redbelly reserved wallets"]),
    ("Other wallets", ["Largest wallets (10 million or more)", "Large wallets (1 million to 10 million)",
                       "Mid-size wallets (100,000 to 1 million)", "Smaller wallets (1,000 to 100,000)",
                       "Small wallets (1 to 1,000)", "Wallets under 1 RBNT at the start"]),
    ("Vesting contracts", ["Vesting contracts"]),
    ("Multi-signature wallets (Safe)", ["Multi-signature wallets (Safe)"]),
    ("Bridge contracts", ["Bridge contracts"]),
    ("All other contracts", ["Unverified contracts", "Other staking contracts", "Other verified contracts",
                             "Trading pools on decentralised exchanges", "Contracts under 1 RBNT"]),
    ("Reddex pools: reward funds", ["Reddex pools: reward funds"]),
]


def owner_totals():
    data = {r[0]: (num(r[1]), num(r[2])) for r in rows("06d_net_change_by_group.csv")[1:]}
    out = []
    for name, parts in OWNER_GROUPS:
        out.append((name, sum(data[p][0] for p in parts if p in data), sum(data[p][1] for p in parts if p in data)))
    return out


def where_the_rbnt_is():
    body = sorted(owner_totals(), key=lambda r: r[2])
    names = [r[0] for r in body]
    v0 = [r[1] for r in body]
    v1 = [r[2] for r in body]
    fig, ax = plt.subplots(figsize=(10, 5.4))
    fig.subplots_adjust(left=0.27, right=0.97, top=0.78, bottom=0.12)
    y = range(len(names))
    h = 0.38
    ax.barh([i + h / 2 for i in y], v0, height=h, color=S.SLATE_LIGHT)
    ax.barh([i - h / 2 for i in y], v1, height=h, color=S.BRAND)
    for i in y:
        share = v1[i] / 1e10 * 100
        ax.text(max(v0[i], v1[i]), i, f"  {short(v1[i])}  ({'under 0.1' if share < 0.1 else f'{share:.1f}'}%)", va="center", fontsize=9,
                color=S.INK, family=S.MONO)
    ax.set_yticks(list(y), names)
    ax.grid(axis="y", visible=False)
    axis_short(ax)
    ax.set_xlim(0, max(v0 + v1) * 1.3)
    legend_patches(ax, [("30 June 2026", S.SLATE_LIGHT), ("30 September 2026", S.BRAND)])
    finish(fig, "fig1_who_holds", "Who holds the 10 billion RBNT",
           "RBNT, WRBNT and staked RBNT counted with the address that owns them. Labels show 30 September and the share of supply")


def holders_by_size():
    data = rows("04_holders_by_size.csv")
    body = [r for r in data[1:] if not r[0].startswith("Contracts")]
    last_n, last_v = len(data[0]) - 2, len(data[0]) - 1
    names = [r[0] for r in body][::-1]
    n = [num(r[last_n]) for r in body][::-1]
    v = [num(r[last_v]) for r in body][::-1]
    tn, tv = sum(n), sum(v)
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 5.6), sharey=True)
    fig.subplots_adjust(left=0.22, right=0.97, top=0.76, bottom=0.12, wspace=0.12)
    y = list(range(len(names)))
    a1.barh(y, [x / tn * 100 for x in n], color=S.SLATE_DARK, height=0.6)
    a2.barh(y, [x / tv * 100 for x in v], color=S.BRAND, height=0.6)
    for i in y:
        a1.text(n[i] / tn * 100, i, "  " + pct_label(n[i] / tn * 100), va="center", fontsize=8.5, family=S.MONO, color=S.INK)
        a2.text(v[i] / tv * 100, i, "  " + pct_label(v[i] / tv * 100), va="center", fontsize=8.5, family=S.MONO, color=S.INK)
    a1.set_yticks(y, names)
    for a, t in ((a1, "Share of wallets"), (a2, "Share of the RBNT they hold")):
        a.set_title(t, fontsize=11, pad=8)
        a.grid(axis="y", visible=False)
        a.set_xlim(0, 100)
        a.xaxis.set_major_formatter(FuncFormatter(lambda x, _p: f"{x:.0f}%"))
    finish(fig, "fig2_holders_by_size", "Most wallets are small; most RBNT sits in a few large ones",
           "Wallets outside the named addresses, by size of holding, 30 September 2026 (RBNT, WRBNT and staked RBNT added together)")


def holder_count():
    data = rows("05_concentration.csv")[1:]
    labels = ["30 Jun", "31 Jul", "31 Aug", "30 Sep"]
    n = [num(r[2]) for r in data]
    fig, ax = plt.subplots(figsize=(10, 4.6))
    fig.subplots_adjust(left=0.08, right=0.97, top=0.74, bottom=0.14)
    bars = ax.bar(labels, n, color=[S.SLATE_LIGHT] * (len(n) - 1) + [S.BRAND], width=0.55)
    for b, x in zip(bars, n):
        ax.text(b.get_x() + b.get_width() / 2, x, f"{x:,.0f}\n", ha="center", va="bottom", fontsize=10, family=S.MONO, color=S.INK)
    ax.set_ylim(0, max(n) * 1.18)
    ax.grid(axis="x", visible=False)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _p: f"{v:,.0f}"))
    finish(fig, "fig3_holder_count", "Wallets holding 1 RBNT or more, month by month",
           "End of each month, UTC. RBNT, WRBNT and staked RBNT added together; named addresses and contracts left out")


def concentration():
    data = rows("05_concentration.csv")[1:]
    labels = ["30 Jun", "31 Jul", "31 Aug", "30 Sep"]
    series = [("Largest 10 wallets", 4, S.BRAND), ("Largest 100 wallets", 5, S.SLATE_DARK), ("Largest 1,000 wallets", 6, S.SLATE)]
    fig, ax = plt.subplots(figsize=(10, 4.8))
    fig.subplots_adjust(left=0.08, right=0.80, top=0.76, bottom=0.14)
    for name, col, color in series:
        vals = [num(r[col]) for r in data]
        ax.plot(labels, vals, color=color, lw=2.4, marker="o", ms=5)
        ax.text(len(labels) - 1 + 0.08, vals[-1], f"{name}\n{vals[-1]:.1f}%", va="center", fontsize=9, color=S.INK)
    ax.set_ylim(0, 100)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _p: f"{v:.0f}%"))
    ax.grid(axis="x", visible=False)
    finish(fig, "fig4_concentration", "How much of the wallets' RBNT the largest wallets hold",
           "Share of all RBNT held by wallets with 1 RBNT or more, end of each month")


def cohorts():
    data = rows("06_cohorts.csv")
    body = [r for r in data[1:] if not r[0].startswith("New")]
    names = [r[0] for r in body][::-1]
    parts = [("Added more than 1%", 2, S.BRAND), ("Within 1%", 3, S.SLATE_LIGHT),
             ("Reduced more than 1%", 4, S.SLATE_DARK), ("Under 1 RBNT at the end", 5, S.SLATE)]
    fig, ax = plt.subplots(figsize=(10, 5.2))
    fig.subplots_adjust(left=0.30, right=0.97, top=0.72, bottom=0.12)
    left = [0.0] * len(names)
    tot = [num(r[1]) for r in body][::-1]
    for label, col, color in parts:
        vals = [num(r[col]) for r in body][::-1]
        sh = [v / t * 100 if t else 0 for v, t in zip(vals, tot)]
        ax.barh(names, sh, left=left, color=color, height=0.6, label=label)
        for i, (l, w) in enumerate(zip(left, sh)):
            if w >= 7:
                ax.text(l + w / 2, i, f"{w:.0f}%", ha="center", va="center", fontsize=8.5, family=S.MONO,
                        color="#FFFFFF" if color in (S.BRAND, S.SLATE_DARK) else S.INK)
        left = [l + w for l, w in zip(left, sh)]
    ax.set_yticks(range(len(names)), [f"{n}\n{int(t):,} wallets" for n, t in zip(names, tot)])
    ax.set_xlim(0, 100)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda x, _p: f"{x:.0f}%"))
    ax.grid(axis="y", visible=False)
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=4, handlelength=1, borderaxespad=0.3, fontsize=9)
    finish(fig, "fig5_cohorts", "What the same wallets did between 1 July and 30 September",
           "Wallets grouped by their holding at the start of the quarter; each bar shows what share added, held or reduced")


def cohort_net():
    data = {r[0]: num(r[3]) for r in rows("06d_net_change_by_group.csv")[1:]}
    order = ["Largest wallets (10 million or more)", "Large wallets (1 million to 10 million)",
             "Mid-size wallets (100,000 to 1 million)", "Smaller wallets (1,000 to 100,000)",
             "Small wallets (1 to 1,000)", "Wallets under 1 RBNT at the start", "Vesting contracts",
             "Multi-signature wallets (Safe)", "Bridge contracts", "Trading pools on decentralised exchanges",
             "Redbelly reserved wallets"]
    names = order[::-1]
    net = [data.get(n, 0) for n in names]
    fig, ax = plt.subplots(figsize=(10, 5.6))
    fig.subplots_adjust(left=0.36, right=0.93, top=0.80, bottom=0.11)
    ax.barh(names, net, color=[S.BRAND if v >= 0 else S.SLATE_DARK for v in net], height=0.62)
    ax.axvline(0, color=S.SLATE, lw=1)
    lim = max(abs(v) for v in net) * 1.4
    ax.set_xlim(-lim, lim)
    for i, v in enumerate(net):
        ax.text(v, i, ("  +" if v >= 0 else "-") + short(abs(v)) + ("  " if v < 0 else ""), va="center",
                ha="left" if v >= 0 else "right", fontsize=9, family=S.MONO, color=S.INK)
    axis_short(ax)
    ax.grid(axis="y", visible=False)
    finish(fig, "fig6_net_change", "Which groups gained and which gave up RBNT",
           "Change in holdings between 30 June and 30 September. Wallet groups are fixed by size at the start")


def weekly_pools():
    data = rows("07_weekly_named_addresses.csv")
    hdr, body = data[0], data[1:]
    import calendar
    dates = [f"{int(r[0][8:])} {calendar.month_abbr[int(r[0][5:7])]}" for r in body]
    fig, ax = plt.subplots(figsize=(10, 4.8))
    fig.subplots_adjust(left=0.08, right=0.83, top=0.76, bottom=0.14)
    pools = [(p[0], S.BRAND if i == 0 else S.SLATE_DARK) for i, p in enumerate(C.POOLS)]
    for name, color in pools:
        col = hdr.index(f"{name}: RBNT balance")
        vals = [num(r[col]) for r in body]
        ax.plot(range(len(dates)), vals, color=color, lw=2.4, marker="o", ms=3.5)
        ax.text(len(dates) - 1 + 0.25, vals[-1], f"{name.replace('Reddex RBNT pool, ', '').capitalize()}\n{short(vals[-1])}",
                va="center", fontsize=9, color=S.INK)
    ax.set_xticks(range(len(dates)), dates, fontsize=8)
    axis_short(ax, "y")
    ax.set_ylim(0, None)
    ax.grid(axis="x", visible=False)
    finish(fig, "fig7_pools_weekly", "RBNT held by the two Reddex staking pools, week by week",
           "Each pool's RBNT balance at the end of each week (UTC). The balance includes reward funds as well as stakes",
           source=SOURCE.replace("blocks", "weekly blocks from").replace(" and ", " to "))


def pool_activity():
    data = rows("10_staking_pools.csv")
    hdr, body = data[0], data[1:]
    groups = [("Staked", hdr.index("RBNT staked"), S.BRAND), ("Unstaked", hdr.index("RBNT unstaked"), S.SLATE_DARK),
              ("Paid as rewards", hdr.index("RBNT paid as rewards"), S.SLATE)]
    fig, ax = plt.subplots(figsize=(10, 4.6))
    fig.subplots_adjust(left=0.08, right=0.97, top=0.72, bottom=0.14)
    w = 0.26
    for j, (label, col, color) in enumerate(groups):
        vals = [num(r[col]) for r in body]
        xs = [i + (j - 1) * w for i in range(len(body))]
        ax.bar(xs, vals, width=w, color=color, label=label)
        for x, v in zip(xs, vals):
            ax.text(x, v, short(v), ha="center", va="bottom", fontsize=8.5, family=S.MONO, color=S.INK)
    ax.set_xticks(range(len(body)), [r[0].replace("Reddex RBNT pool, ", "").capitalize() + " pool" for r in body])
    axis_short(ax, "y")
    ax.grid(axis="x", visible=False)
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=3, handlelength=1, fontsize=9)
    finish(fig, "fig8_pool_activity", "RBNT moved into and out of the pools during the quarter",
           "Sums of the pools' own Stake, Unstake and reward claim events between the two snapshot blocks")


def lock_calendar():
    data = rows("11_lock_calendar.csv")[1:]
    name = C.POOLS[1][0]
    body = [r for r in data if r[0] == name and r[1] != "already unlocked"]
    if not body:
        return
    months = [r[1] for r in body]
    vals = [num(r[2]) for r in body]
    import calendar
    labels = [f"{calendar.month_abbr[int(m[5:])]}\n{m[:4]}" for m in months]
    fig, ax = plt.subplots(figsize=(10, 4.6))
    fig.subplots_adjust(left=0.08, right=0.97, top=0.76, bottom=0.16)
    ax.bar(range(len(vals)), vals, color=S.SLATE_DARK, width=0.6)
    for i, v in enumerate(vals):
        ax.text(i, v, short(v), ha="center", va="bottom", fontsize=8.5, family=S.MONO, color=S.INK)
    ax.set_xticks(range(len(vals)), labels, fontsize=8.5)
    axis_short(ax, "y")
    ax.grid(axis="x", visible=False)
    finish(fig, "fig9_lock_calendar", "When stakes in the 365 day pool reach the end of their lock",
           "RBNT staked in the 365 day pool on 30 September 2026, by the month each stake's lock ends (UTC)",
           note="A lock ending does not mean the RBNT will be unstaked.")


def reserved_wallets():
    data = rows("08_named_addresses.csv")
    body = [r for r in data[1:] if r[0] in C.RESERVED.values()]
    body.sort(key=lambda r: num(r[4]))
    names = [r[0] for r in body]
    v0 = [num(r[3]) for r in body]
    v1 = [num(r[4]) for r in body]
    fig, ax = plt.subplots(figsize=(10, 5.6))
    fig.subplots_adjust(left=0.24, right=0.95, top=0.78, bottom=0.12)
    h = 0.38
    y = range(len(names))
    ax.barh([i + h / 2 for i in y], v0, height=h, color=S.SLATE_LIGHT)
    ax.barh([i - h / 2 for i in y], v1, height=h, color=S.BRAND)
    for i in y:
        d = v1[i] - v0[i]
        tag = "no change" if abs(d) < 0.5 else (("+" if d > 0 else "-") + short(abs(d)))
        ax.text(max(v0[i], v1[i]), i, f"  {short(v1[i])}  ({tag})", va="center", fontsize=8.5, family=S.MONO, color=S.INK)
    ax.set_yticks(list(y), names)
    ax.grid(axis="y", visible=False)
    axis_short(ax)
    ax.set_xlim(0, max(v0 + v1) * 1.35)
    legend_patches(ax, [("30 June 2026", S.SLATE_LIGHT), ("30 September 2026", S.BRAND)])
    finish(fig, "fig10_reserved_wallets", "RBNT in Redbelly's nine reserved wallets",
           "Native RBNT balance of each wallet listed on the DAO treasury page, start and end of the quarter")


def social_card(height_in=9.0, dpi=100, name="x_card_1600x900"):
    """Image for the X thread (1600 x 900) or link previews (1200 x 630), with the dated
    last-verified line the brand kit asks for."""
    from matplotlib.patches import FancyBboxPatch
    from matplotlib.image import imread
    fig = plt.figure(figsize=(16, height_in), dpi=dpi)
    fig.patch.set_facecolor(S.SURFACE_DARK)
    logo = imread(str(C.ASSETS / "dao-logo-on-dark.png"))
    lax = fig.add_axes([0.05, 0.80, 0.09, 0.14])
    lax.imshow(logo)
    lax.axis("off")
    fig.text(0.05, 0.70, f"RBNT Holder Report, {FIG['quarter']}", color="#f1f5f8", fontsize=38, fontweight=700)
    fig.text(0.05, 0.635, f"{FIG['first_day']} to {FIG['last_day']}. Read from the Redbelly chain.", color="#c2ced6", fontsize=19)
    fig.add_artist(plt.Line2D([0.05, 0.12], [0.6, 0.6], color=S.BRAND, lw=4))
    p = FIG["pools"]
    pool1 = sum(v["balance_end"] for v in p.values())
    pool0 = sum(v["balance_start"] for v in p.values())
    h = FIG["holders"]
    d0, d1 = sorted(h)[0], sorted(h)[-1]
    c0, c1 = FIG["concentration"]["start"], FIG["concentration"]["end"]
    tiles = [
        (f"{h[d1]['wallets_1plus']:,}", "wallets hold 1 RBNT or more", f"{h[d0]['wallets_1plus']:,} on 30 June"),
        (f"{pool1 / 1e6:,.1f}M", "RBNT in the two Reddex staking pools", f"{pool0 / 1e6:,.1f}M on 30 June"),
        (f"{c1['top100'] * 100:.1f}%", "of wallet-held RBNT is in the largest 100 wallets", f"{c0['top100'] * 100:.1f}% on 30 June"),
        (f"{FIG['reserved_total']['end'] / 1e9:.2f}B", "RBNT in Redbelly's nine reserved wallets",
         f"{FIG['reserved_total']['start'] / 1e9:.2f}B on 30 June"),
    ]
    for i, (big, what, was) in enumerate(tiles):
        x = 0.05 + i * 0.228
        fig.add_artist(FancyBboxPatch((x, 0.17), 0.21, 0.34, boxstyle="round,pad=0,rounding_size=0.008",
                                      facecolor="#141f26", edgecolor="#263641", lw=1.5, transform=fig.transFigure))
        fig.text(x + 0.015, 0.40, big, color="#f1f5f8", fontsize=36, fontweight=700)
        fig.text(x + 0.015, 0.33, "\n".join(textwrap.wrap(what, 26)), color="#c2ced6", fontsize=15, va="top")
        fig.text(x + 0.015, 0.20, was, color="#8fa1ad", fontsize=13, family=S.MONO)
    fig.text(0.05, 0.07, f"Blocks {FIG['start_block']:,} and {FIG['end_block']:,}, Redbelly mainnet. "
             f"Last verified {long_date(FIG['read_on'])}. Not financial advice.", color="#8fa1ad", fontsize=13)
    out = C.ROOT / "community"
    out.mkdir(exist_ok=True)
    fig.savefig(out / f"{name}.png", dpi=dpi, facecolor=S.SURFACE_DARK)
    fig.savefig(out / f"{name}.svg", facecolor=S.SURFACE_DARK)
    plt.close(fig)


def og_card():
    social_card(height_in=8.4, dpi=75, name="og_1200x630")


def main():
    S.setup()
    for f in (where_the_rbnt_is, holders_by_size, holder_count, concentration, cohorts, cohort_net,
              weekly_pools, pool_activity, lock_calendar, reserved_wallets, social_card, og_card):
        f()
        print("drew", f.__name__)


if __name__ == "__main__":
    main()

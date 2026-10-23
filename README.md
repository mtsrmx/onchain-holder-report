# RBNT Holder Report

A quarterly, sourced report on how RBNT holders behave on the Redbelly chain: who holds the coins, how concentrated holdings are, who added and who reduced, how staking changed, and what the publicly named wallets did. It describes trends in groups and names only addresses that are already public.

**Edition 1 covers Q3 2026 (1 July to 30 September 2026).** On-chain data last verified 23 October 2026.

## What is in this package

| Deliverable | File |
|---|---|
| 1. The report, with charts | `report/RBNT_Holder_Report_Q3_2026.pdf` (also as `report/RBNT_Holder_Report_Q3_2026.html`) |
| 2. Community summary | `community/x_thread.txt` (an X thread, one post per block, posts separated by `---`), `community/community_summary.md` (a few paragraphs), `community/x_card_1600x900.png` and `.svg` (image for the thread) |
| 3. Data behind the charts | `data/*.csv`, also bundled in `data/RBNT_Holder_Report_Q3_2026_data.xlsx`; every number quoted in the text is in `data/figures.json` |
| 3. Method and sources | `METHOD.md` |
| Verification | `data/verification.json` (independent re-reads from the node and file scans), `tests/` |
| Charts on their own | `report/charts/*.svg` and `*.png` |

## The quarter at a glance

* The two Reddex RBNT staking pools held 754.8 million RBNT on 30 September, up from 639.1 million on 30 June (18.1%). Staked RBNT alone went from 635.8 million to 751.3 million.
* Vesting contracts went from 1.68 billion to 1.58 billion RBNT and sent 127.8 million to wallets.
* The 21 wallets that started with 10 million RBNT or more went from 1.06 billion to 1.09 billion: 9 added, 7 stayed within 1%, 5 reduced.
* The largest 100 wallets held 76.7% of all wallet-held RBNT at the end, against 75.8% at the start. 53,574 wallets held 1 RBNT or more, up from 53,417.
* Redbelly's nine reserved wallets went from 5.97 billion to 5.93 billion RBNT. Most of the movement was between reserved wallets; only Ecosystem (Unlocked) sent RBNT outside the group.
* 99.9996% of the 10 billion RBNT supply was found in the balances read.

## How the numbers were made

Everything comes from public chain data, read at fixed blocks: block 3,025,809 (30 June 2026, 23:57:19 UTC) and block 3,209,414 (30 September 2026, 23:57:35 UTC), plus month-end and weekly blocks. We read every transaction receipt and block header since block 0 and every internal transfer to build a list of 761,587 addresses, then read the balance of each from the Redbelly node. WRBNT and staked RBNT are counted with their owner, so each coin is counted once. 57 exact checks run on the data and the build stops if any fails. See `METHOD.md` for every step.

## Repeat it

```
pip install -r requirements.txt
python -m playwright install chromium   # only needed for the PDF
make all                                # fetch, analyse, build, verify
```

To produce the next edition, change the quarter in `holder_report/config.py` and run `make all` again. `METHOD.md` section 5 explains the details.

## Layout

```
holder_report/   shared code: settings, RPC and explorer clients, analysis functions, chart style, report helpers
scripts/         the numbered steps, s01 to s10
tests/           unit tests for the analysis functions
data/            published tables (aggregates only), figures.json, verification.json, spreadsheet
report/          the report (PDF, HTML), its stylesheet and the charts
community/       X thread, summary paragraphs and image
assets/          fonts (Be Vietnam Pro, JetBrains Mono; open licences) and the DAO logo from the Task Board brand kit
cache/           local chain data, created by the scripts; not published because it holds per-address data
```

## Ground rules this report follows

* Only addresses that are already public are named: Redbelly's nine reserved wallets from the DAO treasury page, the Wrapped RBNT contract, the two Reddex RBNT staking pools, and any exchange or contract Routescan labels (none other than WRBNT on 23 October 2026). Every other address is counted only inside a group of at least five.
* No guesses about who controls any address.
* No price forecasts, no investment advice.
* Not financial advice.

Fonts: Be Vietnam Pro and JetBrains Mono, both under the SIL Open Font License. Design follows the Redbelly DAO Task Board brand kit.

# Method and sources

This note explains how the RBNT Holder Report is produced, so that anyone can check this edition or produce the next one. It covers what is measured, where every number comes from, the checks that must pass, and the exact steps to repeat the work.

The first edition covers Q3 2026 (1 July to 30 September 2026). Its data was last verified on 23 October 2026.

## 1. What the report measures

| Question in the brief | How it is measured | Where it appears |
|---|---|---|
| How RBNT holdings are spread and how that changed | Every address's holding at four month-end blocks, grouped into size bands; share held by the largest 10, 100 and 1,000 wallets; Gini coefficient | Sections 2 to 4, `04`, `05` |
| Accumulation and selling among the largest holders | Wallets grouped by size at the start and followed to the end: how many added more than 1%, stayed within 1%, reduced by more than 1%; net change per group; transfers between groups | Section 5, `06`, `06b`, `06d`, `12` |
| Staking trends in the two Reddex pools | Each pool's RBNT balance at the start and end (the headline figure, as the brief asks), weekly balances, the pool's own `totalStake`, stake, unstake and reward events, lock calendar | Section 6, `07`, `10`, `11` |
| Flows in and out of publicly named wallets | Balance of each reserved wallet at both dates and weekly, every transfer in between grouped by counterparty, reconciliation to the last unit | Section 7, `08`, `09` |
| Labelled exchange wallets | Routescan's public address labels | Section 7 (none labelled on 23 October 2026) |

### Definitions

* **Start** is block 3,025,809, the last block before midnight UTC at the end of 30 June 2026. **End** is block 3,209,414, the last block before midnight UTC at the end of 30 September 2026. Month-end and weekly snapshots use the same rule. A snapshot at time T is the highest block whose timestamp is earlier than T.
* **Holding** of an address = native RBNT + WRBNT balance + RBNT staked in either Reddex pool (`userInfo(address).amount`). A holder who wraps or stakes is therefore not counted as having sold.
* **Counted once.** The RBNT inside the WRBNT contract backs WRBNT one to one, and the staked RBNT inside each pool belongs to the stakers. Both are counted with their owners, never again at the contract. The part of a pool's balance above its `totalStake` is that pool's **reward funds**.
* **Named addresses** are the nine reserved wallets on the DAO treasury page, the WRBNT contract, the two Reddex RBNT pools and any address Routescan labels. They are reported by name.
* **Wallet** = an address with no code at the end block (an EIP-7702 delegation marker still counts as a wallet). **Contract** = an address with code. Unlabelled contracts are grouped by the contract name in their verified source on Routescan (vesting manager, Safe multi-signature wallet, trading pool, bridge, staking contract). A kind is shown on its own only if at least five contracts share it; otherwise it is folded into "Other verified contracts".
* **Holder counts** and **concentration** use wallets with at least 1 RBNT. Contracts are left out because one contract can hold coins for many people.
* **Cohorts** (section 5) are fixed by holding at the start: 10 million or more, 1 to 10 million, 100,000 to 1 million, 1,000 to 100,000, and 1 to 1,000 RBNT. The same wallets are followed to the end. "Added" means more than 1% higher, "reduced" more than 1% lower, "within 1%" otherwise, "below 1 at end" means the wallet ended with less than 1 RBNT.

### Pool balances include reward funds

Rewards in both Reddex pools are paid in RBNT from the pool's own balance (see `_claim` in the pools' verified code). A pool's RBNT balance may therefore include reward funds as well as stakes. The headline staking figures are the pools' RBNT balances, read from the chain at the start and end, as the brief asks. The report then splits each balance into staked RBNT (the pool's `totalStake`) and reward funds (balance minus `totalStake`).

### Network fees are credited, not destroyed

Redbelly blocks have the zero address as their miner, yet the total of all balances hardly changes from block to block. During Q3 2026 senders paid 1,999,924 RBNT in fees while all balances together fell by only 11 RBNT. The network credited 1,999,913 RBNT of fees to 219 addresses as balance changes without any transaction. This is why the report reads every balance directly at each snapshot instead of adding up transfers. It also gives a strong completeness test (section 4 below).

## 2. Privacy rules applied

* Only named addresses (listed above) are ever shown with an address or a name.
* Every other address is counted only inside a group of at least five. Size bands with fewer than five wallets are merged (the bands above 10 million RBNT were merged for this reason).
* Contract kinds come from the contract's own verified code, which describes the program, not who controls it. No owner is inferred.
* No label is guessed. Routescan labelled no exchange wallet, so no address is treated as an exchange.
* The local cache that holds per-address data (`cache/chain.sqlite`) is not published. Only aggregates are. `scripts/s10_verify.py` scans every published file and fails if any address outside the named list appears.

## 3. Data sources

| Source | Endpoint | What is read | Used for |
|---|---|---|---|
| Redbelly mainnet RPC, chain ID 151 | `https://governors.mainnet.redbelly.network` | `eth_getBalance`, `eth_call` (`balanceOf`, `totalSupply`, `totalStake`, `userInfo`, `getStakeUnlockTimes`, `owner`), `eth_getBlockReceipts` and `eth_getBlockByNumber` for every block, `eth_getCode` | Every balance and every pool figure in the report |
| Routescan API (Etherscan compatible) | `https://api.routescan.io/v2/network/mainnet/evm/151/etherscan/api` | `txlistinternal` by block range (all 1,753,030 internal transfers since block 0), `getsourcecode`, `getblocknobytime` | Finding addresses reached only by internal transfers; contract kinds; cross-checking snapshot blocks |
| Routescan address list | `https://api.routescan.io/v2/network/mainnet/evm/151/addresses` | The largest addresses and their public names | Finding addresses and labels only. Its balances (today's) are never used |
| Redbelly DAO treasury page | `https://redbellydao.network/treasury/` | Names, addresses and launch allocations of the nine reserved wallets (from the table in the page's script) | Naming the reserved wallets |
| Reddex staking | `https://www.reddex.io/stake` and the pools' verified code on Routescan | The two RBNT pools, their lock periods and how rewards are paid | Staking section |
| Task Board brand kit | `https://taskboard.redbellydao.network/brand` | Colours, type, logo rules, voice | Design of the report and charts |

All sources were read on 23 October 2026. Snapshot block numbers found by binary search on the node matched Routescan's `getblocknobytime` for every snapshot time.

### Named addresses used

| Name | Address | Source |
|---|---|---|
| Team (Locked) | `0xbCee2DEfb7cF136480e3619Cf93E8129059977aF` | DAO treasury page |
| Governance (Locked) | `0x9a83957d3399CBBCbEf2112797B4a5B8e58C63d4` | DAO treasury page |
| Governance (Unlocked) | `0x9E678318539D7C98057e9F89c58fb8f99752FaeA` | DAO treasury page |
| USYD/CSIRO (Locked) | `0xAC27381EF74457c1258d54a808C2461eEdc56270` | DAO treasury page |
| Investors | `0xeF816D556E01BC194AE302999930EAcD6dc4e566` | DAO treasury page |
| Reserve | `0x7473fEAf836b5319D9190d8367991Dc6ef33C16d` | DAO treasury page |
| Ecosystem (Locked) | `0xC5c131572d232512973e79204B93C2c1D57c879D` | DAO treasury page |
| Ecosystem 2 (Unlocked) | `0xE0c701c40166BBD8D5f5Ec33c123F0A03E902DF7` | DAO treasury page |
| Ecosystem (Unlocked) | `0x415cAD8Fc89F75a63C5B830E06460EEcdE083C9F` | DAO treasury page |
| Wrapped RBNT (WRBNT) | `0x6ed1f491e2d31536d6561f6bdb2adc8f092a6076` | Brief; labelled "Wrapped RBNT" on Routescan |
| Reddex RBNT pool, no lock | `0x43A1dc107BBb06dF266278056055AE7Fc5bd2817` | Brief |
| Reddex RBNT pool, 365 day lock | `0x5E8040e85D0E6363D798a43BEa939C026449946d` | Brief |

## 4. Steps

Each step is a script in `scripts/`. Every step saves its progress in `cache/chain.sqlite`, so it can be stopped and restarted.

1. **`s01_snapshots.py`** finds the snapshot blocks (start, end, month ends, weekly) by binary search on block timestamps from the node, and cross-checks each with Routescan's `getblocknobytime`.
2. **`s02_scan_chain.py`** reads `eth_getBlockReceipts` for every block from 0 to the end block. It keeps every sender, recipient and created contract, the fee paid per block (gas used times effective gas price), the logs of WRBNT and the two pools, and every receipt inside the quarter. Requests are sized so no batch holds more than 1,500 receipts.
3. **`s02b_block_headers.py`** reads every block header and collects the 20-byte addresses in `extraData` (Redbelly puts its governor set there). Some of these addresses hold RBNT without ever sending or receiving a transaction.
4. **`s03_internal_transfers.py`** pages through Routescan's `txlistinternal` by block range from block 0 to the end block.
5. **`s04_explorer_list.py`** pages through Routescan's address list (it stops after about 10,000 addresses, the largest by today's balance) and records any public names.
6. **`s05_quarter_transactions.py`** reads every block inside the quarter with full transactions, to get the RBNT value of each transaction.
7. **`s06_balances.py`** reads, at the snapshot blocks: native RBNT of every candidate address (761,587 for this edition) at the four month ends; native RBNT of named addresses weekly; WRBNT `balanceOf` of every address that ever touched WRBNT and WRBNT `totalSupply`; `userInfo` of every address that ever staked and each pool's `totalStake` and `owner`; `getStakeUnlockTimes` for every open stake at the end; and `eth_getCode` at the end block for every address that held anything.
8. **`s06b_contract_types.py`** reads the verified contract name of every contract that held at least 1 RBNT.
9. **`s07_analyse.py`** builds the tables in `data/` and `data/figures.json`, and runs 57 exact checks (below). It stops if any fails.
10. **`s08_charts.py`** draws every chart from the CSV files.
11. **`s09_build_report.py`** writes the report (HTML and PDF), the community summary and the spreadsheet. Every number in the text is read from `figures.json` or a CSV; none is typed by hand.
12. **`s10_verify.py`** re-reads headline figures straight from the node, re-reads 600 random cached balances, re-checks the snapshot boundaries, scans every published file for unnamed addresses, dashes, emoji and prices, and checks the X thread fits 280 characters per post. Results go to `data/verification.json`.

### Checks that must pass

All are exact equalities in wei (1 RBNT = 10^18 wei).

* WRBNT `totalSupply` equals the RBNT held by the WRBNT contract, and equals the sum of every WRBNT balance, at every month end.
* For each pool, the stakers' `userInfo` amounts add up to `totalStake` at every month end; stakes minus unstakes in the quarter equal the change in `totalStake`; plain transfers into the pool equal money in minus stakes; the lock calendar adds up to `totalStake`.
* Every group used in sections 1 and 2 adds up to the 10 billion supply at every month end, and the net changes of all groups add up to zero.
* Each wallet group's start and end totals match the sum over its members at the month-end snapshots.
* Every named address reconciles: start balance + transfers in - transfers out - fees paid = end balance.
* Across all addresses, no address lost RBNT that no transfer or fee explains, and the fee credits are no larger than the fees paid.

### Completeness

All 10 billion RBNT were created at genesis in one allocation (block 0). On 30 September 2026 the balances read add up to 9,999,963,515 RBNT, 99.9996% of supply. The remaining 36,485 RBNT changed by only 11 RBNT during the quarter, so it cannot affect any trend.

## 5. How to produce the next edition

1. Install Python 3.11 or later and the packages in `requirements.txt` (`pip install -r requirements.txt`). Chromium is needed for the PDF (`python -m playwright install chromium`, or point `holder_report/htmlkit.py` at an existing Chromium).
2. In `holder_report/config.py`, change `QUARTER` (label, first and last day, `start_ts`, `end_ts`) and `MONTHLY_TS` to the new quarter (`WEEKLY_TS` follows `QUARTER` by itself). If the DAO treasury page has changed, update `RESERVED_WALLETS`.
3. Keep `cache/` to save time, or delete it for a fully independent run. With the cache kept, every step reads only what is new: the chain and header scans and the internal transfer download continue from the last block they read, balances are read for the new snapshot blocks, and the Routescan list is read again so labels are current.
4. Run `make all` (or the scripts in order). A full run from an empty cache reads about 3.2 million blocks and 760,000 addresses and takes roughly an hour on the public endpoints.
5. Read the report end to end. The text is generated, but each sentence was written for this quarter's pattern; a few sentences assert what they claim (for example that only one address is labelled on Routescan) and the build stops if that is no longer true, so the sentence can be rewritten.
6. If Routescan has started labelling exchange wallets, they appear in `figures.json` under `labelled_exchanges`. Add them to the named list in `config.py` and extend section 7 with their flows.

## 6. Limits

* The chain shows that coins moved, not who controls an address or why. A fall in a group's holdings may be a sale, a move between a holder's own addresses, or a deposit into a contract.
* One address is not one person. Counts of wallets show how widely RBNT is spread across addresses.
* Internal transfers come from Routescan because the public node has no trace API. They are checked indirectly: every named address, including the WRBNT contract and both pools, which move RBNT almost only through internal transfers, reconciles to the last unit.
* Routescan's address list stops after about 10,000 addresses, so labels below that size would not be seen. The report states this.

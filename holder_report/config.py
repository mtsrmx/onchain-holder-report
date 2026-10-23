"""Settings for one edition of the report.

To produce the next edition, change QUARTER (and the snapshot list if you want
different in-quarter points). Everything else is derived from the chain.
"""
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "cache"
DATA = ROOT / "data"
REPORT = ROOT / "report"
ASSETS = ROOT / "assets"

RPC_URL = "https://governors.mainnet.redbelly.network"
CHAIN_ID = 151
EXPLORER_API = "https://api.routescan.io/v2/network/mainnet/evm/151/etherscan/api"
EXPLORER_V2 = "https://api.routescan.io/v2/network/mainnet/evm/151"
EXPLORER_UI = "https://redbelly.routescan.io"
TREASURY_PAGE = "https://redbellydao.network/treasury/"

TOTAL_SUPPLY_RBNT = 10_000_000_000
WEI = 10**18


def utc(y, m, d):
    return int(datetime(y, m, d, tzinfo=timezone.utc).timestamp())


QUARTER = {
    "label": "Q3 2026",
    "first_day": "1 July 2026",
    "last_day": "30 September 2026",
    # A snapshot at time T is the last block with a timestamp before T.
    "start_ts": utc(2026, 7, 1),
    "end_ts": utc(2026, 10, 1),
}

# Month-end snapshots used for the full holder distribution (four points).
MONTHLY_TS = [utc(2026, 7, 1), utc(2026, 8, 1), utc(2026, 9, 1), utc(2026, 10, 1)]

# Weekly snapshots (every 7 days from the start, plus the end) for the named
# wallets, the staking pools and the WRBNT supply.
WEEKLY_TS = sorted(set([QUARTER["start_ts"] + 7 * 86400 * i for i in range(13)] + [QUARTER["end_ts"]]))
WEEKLY_TS = [t for t in WEEKLY_TS if t <= QUARTER["end_ts"]]

# Wallets Redbelly has publicly named on the DAO treasury page, with the
# allocation the page lists (RBNT). "Ecosystem 2 (Unlocked)" has no listed
# allocation on the page.
RESERVED_WALLETS = [
    ("Team (Locked)", "0xbCee2DEfb7cF136480e3619Cf93E8129059977aF", 1_000_000_000),
    ("Governance (Locked)", "0x9a83957d3399CBBCbEf2112797B4a5B8e58C63d4", 200_000_000),
    ("Governance (Unlocked)", "0x9E678318539D7C98057e9F89c58fb8f99752FaeA", 100_000_000),
    ("USYD/CSIRO (Locked)", "0xAC27381EF74457c1258d54a808C2461eEdc56270", 200_000_000),
    ("Investors", "0xeF816D556E01BC194AE302999930EAcD6dc4e566", 2_785_987_083),
    ("Reserve", "0x7473fEAf836b5319D9190d8367991Dc6ef33C16d", 2_000_000_000),
    ("Ecosystem (Locked)", "0xC5c131572d232512973e79204B93C2c1D57c879D", 2_794_132_788),
    ("Ecosystem 2 (Unlocked)", "0xE0c701c40166BBD8D5f5Ec33c123F0A03E902DF7", None),
    ("Ecosystem (Unlocked)", "0x415cAD8Fc89F75a63C5B830E06460EEcdE083C9F", 919_880_129),
]

WRBNT = "0x6ed1f491e2d31536d6561f6bdb2adc8f092a6076"

POOLS = [
    ("Reddex RBNT pool, no lock", "0x43A1dc107BBb06dF266278056055AE7Fc5bd2817", "no lock"),
    ("Reddex RBNT pool, 365 day lock", "0x5E8040e85D0E6363D798a43BEa939C026449946d", "365 days"),
]

# Smallest group the report will describe on its own. Groups smaller than
# this are merged into the next group so no single unlabelled holder can be
# picked out from a total.
MIN_GROUP = 5


def lower(a):
    return a.lower()


RESERVED = {lower(a): name for name, a, _ in RESERVED_WALLETS}
POOL_ADDRS = {lower(a): name for name, a, _ in POOLS}

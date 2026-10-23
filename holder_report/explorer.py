"""Routescan explorer client (Etherscan compatible API and the v2 REST API).

Used to find addresses and to read internal transfers, which the public node
cannot trace. Balances are never taken from the explorer; they come from the
node at the snapshot blocks.
"""
import time

import requests

from .config import EXPLORER_API, EXPLORER_V2

_s = requests.Session()
PAUSE = 0.25


def _get(url, params=None, retries=10):
    delay = 2.0
    last = None
    for _ in range(retries):
        try:
            r = _s.get(url, params=params, timeout=120)
            if r.status_code == 429 or r.status_code >= 500:
                raise RuntimeError(f"HTTP {r.status_code}")
            d = r.json()
            time.sleep(PAUSE)
            return d
        except (requests.RequestException, RuntimeError, ValueError) as e:
            last = e
            time.sleep(delay)
            delay = min(delay * 2, 120)
    raise RuntimeError(f"explorer gave up: {last}")


def api(**params):
    d = _get(EXPLORER_API, params)
    if d.get("status") == "1":
        return d["result"]
    msg = str(d.get("message", "")) + " " + str(d.get("result", ""))
    if "No transactions found" in msg or "No records found" in msg or d.get("result") == []:
        return []
    raise RuntimeError(f"explorer error for {params}: {msg[:300]}")


def v2(path, **params):
    return _get(EXPLORER_V2 + path, params)


def source_code(address):
    r = api(module="contract", action="getsourcecode", address=address)
    return r[0] if r else None

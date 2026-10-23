"""Small JSON-RPC client for the Redbelly mainnet node.

The public node accepts batches of up to 100 calls. Calls are retried with
backoff; a call that still fails raises, so no gap is ever filled with a guess.
"""
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import requests

from .config import RPC_URL

MAX_BATCH = 100
_local = threading.local()


def _session():
    s = getattr(_local, "s", None)
    if s is None:
        s = requests.Session()
        _local.s = s
    return s


class RPCError(RuntimeError):
    pass


def batch(calls, url=RPC_URL, retries=8):
    """Run up to 100 (method, params) calls in one request. Returns results in order."""
    assert len(calls) <= MAX_BATCH
    payload = [{"jsonrpc": "2.0", "id": i, "method": m, "params": p} for i, (m, p) in enumerate(calls)]
    delay = 1.0
    last = None
    for _ in range(retries):
        try:
            r = _session().post(url, data=json.dumps(payload), headers={"content-type": "application/json"}, timeout=180)
            if r.status_code != 200:
                raise RPCError(f"HTTP {r.status_code}: {r.text[:200]}")
            out = r.json()
            if isinstance(out, dict):
                raise RPCError(str(out)[:300])
            by_id = {x["id"]: x for x in out}
            res = []
            for i in range(len(calls)):
                x = by_id.get(i)
                if x is None or "error" in x:
                    raise RPCError(f"{calls[i][0]} {calls[i][1]}: {x and x.get('error')}")
                res.append(x["result"])
            return res
        except (requests.RequestException, RPCError, ValueError) as e:
            last = e
            time.sleep(delay)
            delay = min(delay * 2, 30)
    raise RPCError(f"gave up after {retries} tries: {last}")


def call(method, params):
    return batch([(method, params)])[0]


def run_all(calls, workers=16, progress=None):
    """Run any number of calls, 100 per request, in parallel. Results in order."""
    chunks = [calls[i:i + MAX_BATCH] for i in range(0, len(calls), MAX_BATCH)]
    out = [None] * len(chunks)
    done = 0
    with ThreadPoolExecutor(workers) as ex:
        futs = {ex.submit(batch, c): i for i, c in enumerate(chunks)}
        for f, i in futs.items():
            out[i] = f.result()
            done += 1
            if progress and done % 200 == 0:
                progress(done, len(chunks))
    return [r for chunk in out for r in chunk]


def hx(n):
    return hex(n)


def block_ts(number):
    b = call("eth_getBlockByNumber", [hex(number), False])
    return int(b["timestamp"], 16)


def head():
    return int(call("eth_blockNumber", []), 16)


def last_block_before(ts, lo=0, hi=None):
    """Highest block number whose timestamp is strictly before ts (binary search on the node)."""
    if hi is None:
        hi = head()
    if block_ts(hi) < ts:
        raise RPCError("chain head is not past the requested time yet")
    while lo + 1 < hi:
        mid = (lo + hi) // 2
        if block_ts(mid) < ts:
            lo = mid
        else:
            hi = mid
    return lo


# ABI helpers (no external dependency)
def selector(sig):
    from Crypto.Hash import keccak
    k = keccak.new(digest_bits=256)
    k.update(sig.encode())
    return "0x" + k.hexdigest()[:8]


def topic(sig):
    from Crypto.Hash import keccak
    k = keccak.new(digest_bits=256)
    k.update(sig.encode())
    return "0x" + k.hexdigest()


def enc_address(a):
    return a.lower().replace("0x", "").rjust(64, "0")


def words(hexdata):
    h = hexdata[2:] if hexdata.startswith("0x") else hexdata
    return [int(h[i:i + 64], 16) for i in range(0, len(h), 64)]

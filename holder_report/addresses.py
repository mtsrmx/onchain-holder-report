"""Build the set of every address that could hold RBNT, WRBNT or a stake."""
from . import config as C
from .rpc import topic

T_TRANSFER = topic("Transfer(address,address,uint256)")
T_DEPOSIT = topic("Deposit(address,uint256)")
T_WITHDRAWAL = topic("Withdrawal(address,uint256)")
T_STAKE = topic("Stake(address,uint256,uint256,uint256)")
T_UNSTAKE = topic("Unstake(address,uint256,uint256,uint256)")
T_CLAIM = topic("ClaimLiquidXReward(address,uint256)")


def topic_addr(t):
    return "0x" + t[-40:].lower()


def data_addr(data, word=0):
    h = data[2:]
    return "0x" + h[word * 64:(word + 1) * 64][-40:].lower()


def wrbnt_participants(db):
    out = set()
    for t0, t1, t2 in db.execute("SELECT t0, t1, t2 FROM logs WHERE address=?", (C.WRBNT.lower(),)):
        if t0 == T_TRANSFER:
            out.add(topic_addr(t1))
            out.add(topic_addr(t2))
        elif t0 in (T_DEPOSIT, T_WITHDRAWAL):
            out.add(topic_addr(t1))
    return out


def pool_stakers(db, pool):
    out = set()
    for (data,) in db.execute("SELECT data FROM logs WHERE address=? AND t0=?", (pool.lower(), T_STAKE)):
        out.add(data_addr(data))
    return out


def candidates(db):
    s = {a for (a,) in db.execute("SELECT address FROM seen")}
    for a, b, c in db.execute("SELECT sender, recipient, created FROM internal"):
        s.update((a, b, c))
    s |= {a for (a,) in db.execute("SELECT address FROM explorer_list")}
    s |= set(C.RESERVED) | set(C.POOL_ADDRS) | {C.WRBNT.lower()}
    s |= wrbnt_participants(db)
    for p in C.POOL_ADDRS:
        s |= pool_stakers(db, p)
    s.discard("")
    s.discard(None)
    return sorted(s)

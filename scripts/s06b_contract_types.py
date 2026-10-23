"""Step 6b. Read what each RBNT-holding contract is, from its verified source code.

Routescan publishes the verified source of many contracts. The contract name
in that source (for example a vesting manager or a multi-signature wallet)
says what kind of program the address is. It says nothing about who controls
it. The report uses these names only to group contracts by kind, and only for
kinds with at least five contracts.
"""
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from holder_report import explorer, store  # noqa: E402


def main():
    db = store.connect()
    # Contracts that held at least 1 RBNT (native, WRBNT or staked) at any month-end snapshot.
    contracts = [a for (a,) in db.execute(
        "SELECT address FROM code WHERE is_contract=1 AND address NOT IN (SELECT address FROM contract_meta) "
        "AND address IN (SELECT address FROM (SELECT address, block, wei FROM native UNION ALL "
        "SELECT address, block, wei FROM wrbnt UNION ALL SELECT address, block, wei FROM staked) "
        "GROUP BY address, block HAVING sum(CAST(wei AS REAL)) >= 1e18)")]
    for i, a in enumerate(contracts, 1):
        s = explorer.source_code(a) or {}
        src = s.get("SourceCode") or ""
        name = s.get("ContractName") or ""
        db.execute("INSERT OR REPLACE INTO contract_meta VALUES (?,?,?,?)",
                   (a, name, 1 if src else 0, hashlib.sha256(src.encode()).hexdigest() if src else ""))
        if i % 25 == 0:
            db.commit()
            print(f"{i:,}/{len(contracts):,}", flush=True)
    db.commit()
    print("done")


if __name__ == "__main__":
    main()

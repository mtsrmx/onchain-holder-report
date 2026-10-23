"""Step 4. Page through Routescan's list of every address with a balance.

Used for two things only: to make sure no address is missed, and to read the
public names Routescan gives addresses (that is what "labelled on Routescan"
means in this report). The listed balances are today's balances and are not
used for any figure.
Resumable.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from holder_report import explorer, store  # noqa: E402


def main():
    db = store.connect()
    token = store.get_progress(db, "list_next", "")
    page = int(store.get_progress(db, "list_page", 0))
    if token == "DONE":
        # A finished list is read again from the top, so labels are always current.
        token, page = "", 0
    while True:
        params = {"limit": 100, "count": "true"}
        if token:
            params["next"] = token
        d = explorer.v2("/addresses", **params)
        if "items" not in d:
            raise RuntimeError(str(d)[:300])
        if page == 0:
            store.kv_set(db, "explorer_address_count", d.get("count"))
        db.executemany("INSERT OR REPLACE INTO explorer_list VALUES (?,?,?,?)",
                       [(x["address"].lower(), x.get("balance"), x.get("name"), page) for x in d["items"]])
        page += 1
        token = (d.get("link") or {}).get("nextToken") or "DONE"
        store.set_progress(db, "list_next", token)
        store.set_progress(db, "list_page", page)
        db.commit()
        if page % 50 == 0:
            n = db.execute("SELECT count(*) FROM explorer_list").fetchone()[0]
            print(f"page {page:,}: {n:,} addresses, last listed balance {d['items'][-1]['balance'] if d['items'] else '-'}", flush=True)
        if token == "DONE":
            break
    print("done")


if __name__ == "__main__":
    main()

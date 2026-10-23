# Rebuild the whole edition from the chain. Steps are resumable; re-running
# a finished step is quick because its progress is saved in cache/.
PY ?= python3

all: fetch analyse build verify

fetch:
	$(PY) scripts/s01_snapshots.py
	$(PY) scripts/s02_scan_chain.py
	$(PY) scripts/s03_internal_transfers.py
	$(PY) scripts/s04_explorer_list.py
	$(PY) scripts/s05_quarter_transactions.py
	$(PY) scripts/s06_balances.py

analyse:
	$(PY) scripts/s07_analyse.py

build:
	$(PY) scripts/s08_charts.py
	$(PY) scripts/s09_build_report.py

verify:
	$(PY) -m pytest -q tests
	$(PY) scripts/s10_verify.py

.PHONY: all fetch analyse build verify

PY ?= python

.PHONY: setup test reproduce rerun-offline followups

setup:            ## fetch the harness at the paper's commit and apply our patch
	bash tools/get_harness.sh

test: setup       ## unit tests (TV, noise floor, byte-exact prompt edits, discretisation, scripted speaker)
	$(PY) -m pytest -q tests

reproduce: setup  ## recompute every number, table and figure of the paper from the logged replies (no model calls)
	$(PY) -W ignore -m p1 stage8
	$(PY) -W ignore -m p1.refree_check
	$(PY) -W ignore -m p1.c0prime_report

rerun-offline: setup  ## re-run Algorithm 1 (stages 3-8) from scratch; every call is answered by data/cache.sqlite
	PY=$(PY) bash tools/run_core.sh

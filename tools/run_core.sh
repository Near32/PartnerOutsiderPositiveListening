#!/usr/bin/env bash
# Run Algorithm 1 end to end (stages 3-8). Every model call is looked up in data/cache.sqlite first, so with the
# shipped cache this needs no API key and no GPU. Stage 5a (paraphrases) only needs the paraphraser server for
# calls that are not cached: set PARAPHRASER_PY to a Python with torch + transformers to start it automatically.
set -uo pipefail
cd "$(dirname "$0")/.."
PY=${PY:-python}
step() { echo "== $1"; $PY -W ignore -m p1 "$1" || { echo "FAILED $1"; exit 1; }; }
step stage3; step stage4
if [ -n "${PARAPHRASER_PY:-}" ]; then
  $PARAPHRASER_PY tools/hf_server.py > data/hf_server.log 2>&1 & SERVER=$!
  until grep -q serving data/hf_server.log; do grep -q Traceback data/hf_server.log && exit 1; sleep 2; done
fi
step stage5a; [ -n "${SERVER:-}" ] && kill "$SERVER"
step stage5b; step stage6; step stage7; step stage8
echo "core complete: results.md, results/"

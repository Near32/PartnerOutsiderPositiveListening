#!/usr/bin/env bash
# Run an experiment so that at least MIN_FREE_GB of RAM stays free (Kevin's rule, 2026-10-25).
#   1. The command runs in its own user cgroup, capped at MemTotal - MIN_FREE_GB, no swap.
#   2. A watchdog reads MemAvailable every 2 s. The cgroup cannot see the Ollama service's memory
#      (a separate system service; on this APU its GPU memory is system RAM), so if MemAvailable
#      falls below MIN_FREE_GB the watchdog stops the command and unloads every Ollama model.
# Usage: tools/guard.sh <command> [args...]
set -u
MIN_FREE_KB=$(( ${MIN_FREE_GB:-10} * 1024 * 1024 ))
avail() { awk '/MemAvailable/{print $2}' /proc/meminfo; }
unload_ollama() {
  ollama ps 2>/dev/null | awk 'NR>1{print $1}' | while read -r m; do
    curl -s --max-time 30 localhost:11434/api/generate -d "{\"model\":\"$m\",\"keep_alive\":0}" >/dev/null
    echo "guard: unloaded $m" >&2
  done
}
if [ "$(avail)" -lt "$MIN_FREE_KB" ]; then
  echo "guard: only $(( $(avail) / 1024 )) MB available (< ${MIN_FREE_GB:-10} GB); not starting" >&2
  exit 1
fi
total=$(awk '/MemTotal/{print $2}' /proc/meminfo)
systemd-run --user --scope --quiet -p MemoryMax=$(( total - MIN_FREE_KB ))K -p MemorySwapMax=0 "$@" &
pid=$!
trap 'kill -TERM $pid 2>/dev/null' INT TERM
while kill -0 "$pid" 2>/dev/null; do
  a=$(avail)
  if [ "$a" -lt "$MIN_FREE_KB" ]; then
    echo "guard: MemAvailable $(( a / 1024 )) MB < ${MIN_FREE_GB:-10} GB: stopping the experiment" >&2
    kill -TERM "$pid" 2>/dev/null
    unload_ollama
    wait "$pid"
    exit 137
  fi
  sleep 2
done
wait "$pid"

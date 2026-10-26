#!/usr/bin/env bash
# Fetch the double-auction harness of Agrawal et al. (2025) at the exact commit used in the paper,
# and apply our changes (M2, M5, M7-M9; see README.md). The harness is not redistributed here.
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -d harness/.git ] || [ -d harness/src ]; then echo "harness/ already present"; exit 0; fi
git clone --quiet https://github.com/andyjliu/llm-agent-collusion harness
git -C harness checkout --quiet 2bb2a7e22860160d1fddb5d2e5cb460cc6ec6aff
git apply harness.patch
echo "harness ready at commit 2bb2a7e with harness.patch applied"

"""python -m p1 <stage0..stage8> [--config config.yaml] [--model SPEC]   (see README.md)"""
import argparse

from p1.client import Client
from p1.common import ROOT, load_config

ap = argparse.ArgumentParser()
ap.add_argument("cmd")
ap.add_argument("--config", default=str(ROOT / "config.yaml"))
ap.add_argument("--model", help="model spec override for stage0 (dev smoke)")
a = ap.parse_args()
cfg = load_config(a.config)
client = Client(cfg)

from p1 import stages  # noqa: E402  (imports the harness, which changes cwd)

if a.cmd == "stage0":
    stages.stage0(client, cfg, a.model)
elif a.cmd in stages.STAGES:
    stages.STAGES[a.cmd](client, cfg)
else:
    raise SystemExit(f"unknown command {a.cmd}; expected one of {sorted(stages.STAGES)}")

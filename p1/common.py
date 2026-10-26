"""Config, paths, JSONL, ledger and budget helpers shared by every stage."""
import csv
import datetime
import json
import os
import shutil
from pathlib import Path

import yaml

CODE = Path(__file__).resolve().parents[1]
ROOT = Path(os.environ.get("P1_ROOT", CODE))  # outputs + config; override only for dry runs


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def load_yaml(path):
    return yaml.safe_load(Path(path).read_text())


def load_config(path=ROOT / "config.yaml"):
    cfg = load_yaml(path)
    cfg["data_dir"] = ROOT / cfg["data_dir"]
    cfg["results_dir"] = ROOT / cfg["results_dir"]
    cfg["data_dir"].mkdir(parents=True, exist_ok=True)
    cfg["results_dir"].mkdir(parents=True, exist_ok=True)
    # Follow-ups live in their own folder but share the append-only call cache and may read the main runs.
    for k in ("cache_path", "runs_root"):
        if cfg.get(k):
            cfg[k] = Path(cfg[k]) if Path(cfg[k]).is_absolute() else CODE / cfg[k]
    return cfg


def load_prereg(require_receipt=True):
    if require_receipt and not (ROOT / "prereg_receipt.txt").exists():
        raise SystemExit("prereg_receipt.txt missing: run `python -m p1 stage2` first (ground rule 2/3).")
    return load_yaml(ROOT / "prereg.yaml")


def require_model(cfg, key):
    if not cfg.get(key):
        raise SystemExit(f"config.yaml: {key} is null. STOP and ask Kevin (README D4).")
    return cfg[key]


def preserve(path):
    """Never lose data: move an existing file or folder to <its folder>/archive/<name>.<UTC stamp> before it is
    replaced. Returns the archive path (None if nothing existed)."""
    path = Path(path)
    if not path.exists():
        return None
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    dest = path.parent / "archive" / f"{path.name}.{stamp}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(path), str(dest))
    return dest


def write_text_safe(path, text):
    """Write `text`; an existing file with different content is archived first, identical content is left alone."""
    path = Path(path)
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return
    preserve(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def read_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_jsonl(path, rows):
    write_text_safe(path, "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))


def append_jsonl(path, row):
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def check_budget(client, cfg, stage, planned):
    paid = client.paid_calls()
    print(f"[{stage}] planned calls: {planned} (cached calls so far: {paid}, cap: {cfg['max_calls']})")
    if paid + planned > cfg["max_calls"]:
        raise SystemExit(f"[{stage}] would exceed max_calls={cfg['max_calls']}. STOP and ask Kevin (ground rule 4).")


def ledger(stage, planned, actual, retries=0, invalid=0):
    path = ROOT / "ledger.csv"
    new = not path.exists()
    with open(path, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["utc", "stage", "planned_calls", "actual_new_calls", "retries", "invalid"])
        w.writerow([utc(), stage, planned, actual, retries, invalid])

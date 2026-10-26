"""One cached, bounded-concurrency entry point for every model call, API or local GPU.

Every uncached call stores its latency and token usage, so timing.py can turn any
backend's measured throughput into a wall-clock estimate per stage.

ponytail: threads + a per-backend semaphore instead of asyncio. The harness is
thread-based, so one sync code path serves the runs and the replays alike.
"""
import hashlib
import json
import os
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from p1.common import utc


class BudgetExceeded(RuntimeError):
    pass


def call_key(model, temperature, messages, sample_idx, purpose, json_mode, max_tokens, extra=None):
    parts = [model, temperature, messages, sample_idx, purpose, json_mode, max_tokens]
    if extra:  # backend request options (e.g. a reasoning budget); absent for older calls, so their keys are unchanged
        parts.append(extra)
    blob = json.dumps(parts, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode()).hexdigest()


class Client:
    def __init__(self, cfg, db_path=None):
        self.cfg = cfg
        db_path = db_path or cfg.get("cache_path") or cfg["data_dir"] / "cache.sqlite"
        self.db = sqlite3.connect(db_path, check_same_thread=False, isolation_level=None, timeout=60)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("""CREATE TABLE IF NOT EXISTS calls (key TEXT PRIMARY KEY, model TEXT, purpose TEXT,
            sample_idx TEXT, raw TEXT, latency REAL, prompt_tokens INT, completion_tokens INT, utc TEXT,
            stage TEXT, concurrency INT)""")
        self.lock = threading.RLock()  # guards the shared sqlite connection and counters
        self.sems = {b: threading.Semaphore(v.get("max_concurrency", 4)) for b, v in cfg["backends"].items()}
        self.inflight = {b: 0 for b in cfg["backends"]}
        self.sdk = {}
        self.stage = None
        self.new_calls = 0

    def paid_calls(self):
        with self.lock:
            return self.db.execute("SELECT COUNT(*) FROM calls WHERE purpose NOT LIKE 'bench:%'").fetchone()[0]

    def is_cached(self, model, messages, temperature, sample_idx, purpose, json_mode=False, max_tokens=None):
        """True if this exact call is already in the cache (so it costs nothing)."""
        backend = model.split(":", 1)[0]
        max_tokens = max_tokens or self.cfg["backends"][backend].get("max_tokens") or self.cfg["max_tokens"]
        key = call_key(model, temperature, messages, sample_idx, purpose, json_mode, max_tokens,
                       self.cfg["backends"][backend].get("extra_body"))
        return self.cached(key) is not None

    def cached(self, key):
        with self.lock:
            row = self.db.execute("SELECT raw FROM calls WHERE key=?", (key,)).fetchone()
        return row[0] if row else None

    def call(self, model, messages, temperature, sample_idx, purpose, json_mode=False, max_tokens=None):
        max_tokens = max_tokens or self.cfg["backends"][model.split(":", 1)[0]].get("max_tokens") or self.cfg["max_tokens"]
        backend, name = model.split(":", 1)
        extra = self.cfg["backends"][backend].get("extra_body")
        key = call_key(model, temperature, messages, sample_idx, purpose, json_mode, max_tokens, extra)
        raw = self.cached(key)
        if raw is not None:
            return raw
        with self.lock:
            if not purpose.startswith("bench:") and self.paid_calls() >= self.cfg["max_calls"]:
                raise BudgetExceeded(f"max_calls={self.cfg['max_calls']} reached")
        with self.sems[backend]:
            with self.lock:
                self.inflight[backend] += 1
                conc = self.inflight[backend]
            t0 = time.monotonic()
            try:
                for wait in (5, 10, 20, 40, 60, 120, 120, 120, 120, 0):  # provider rate limits: wait, repeat the same request
                    try:
                        raw, pt, ct = self._request(backend, name, messages, temperature, json_mode, max_tokens)
                        break
                    except Exception as e:
                        if "RateLimit" not in type(e).__name__ or not wait:
                            raise
                        print(f"[client] rate limited on {model}; waiting {wait}s", flush=True)
                        time.sleep(wait)
            finally:
                with self.lock:
                    self.inflight[backend] -= 1
            latency = time.monotonic() - t0
        with self.lock:
            self.db.execute("INSERT OR IGNORE INTO calls VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                            (key, model, purpose, json.dumps(sample_idx), raw, latency, pt, ct, utc(),
                             self.stage, conc))
            self.new_calls += 1
            return self.cached(key)  # the first stored reply wins, so every process sees the same sample

    def _sdk(self, backend):
        if backend not in self.sdk:
            b = self.cfg["backends"][backend]
            if backend == "anthropic":
                from anthropic import Anthropic
                self.sdk[backend] = Anthropic(max_retries=8, timeout=600)
            else:
                from openai import OpenAI
                key = b.get("api_key") or (os.environ.get(b["api_key_env"]) if "api_key_env" in b else None)
                if not key and b.get("api_key_file"):  # key kept outside the repo, never logged
                    key = open(os.path.expanduser(b["api_key_file"])).read().strip()
                self.sdk[backend] = OpenAI(base_url=b.get("base_url"), api_key=key, max_retries=8, timeout=1800)
        return self.sdk[backend]

    def _request(self, backend, name, messages, temperature, json_mode, max_tokens):
        sdk = self._sdk(backend)
        if backend == "anthropic":  # same system-prompt default as the harness AnthropicClient
            system, msgs = ((messages[0]["content"], messages[1:]) if messages[0]["role"] == "system"
                            else ("You are a helpful assistant.", messages))
            r = sdk.messages.create(model=name, system=system, messages=msgs, max_tokens=max_tokens,
                                    temperature=temperature, top_p=1.0)
            return r.content[0].text, r.usage.input_tokens, r.usage.output_tokens
        kw = dict(model=name, messages=messages, temperature=temperature, top_p=1.0)
        kw["max_completion_tokens" if backend == "openai" else "max_tokens"] = max_tokens
        if json_mode:
            kw["response_format"] = {"type": "json_object"}
        if self.cfg["backends"][backend].get("extra_body"):
            kw["extra_body"] = self.cfg["backends"][backend]["extra_body"]
        r = sdk.chat.completions.create(**kw)
        u = r.usage
        return r.choices[0].message.content or "", getattr(u, "prompt_tokens", None), getattr(u, "completion_tokens", None)

    def map(self, fn, jobs, workers=None, sink=None):
        """Run fn over jobs with enough threads to saturate every backend semaphore. With `sink`, every
        result is appended to that JSONL file as soon as it completes, so a crash loses nothing; results
        are returned in job order. An existing sink from an earlier run is archived, never overwritten."""
        from concurrent.futures import as_completed
        from p1.common import append_jsonl, preserve
        workers = workers or sum(v.get("max_concurrency", 4) for v in self.cfg["backends"].values())
        if sink:
            preserve(sink)
        lock = threading.Lock()
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(fn, j): i for i, j in enumerate(jobs)}
            out, errors = [None] * len(futs), []
            for f in as_completed(futs):
                try:
                    out[futs[f]] = f.result()
                except Exception as e:  # one failed job must not stop the others from being saved
                    errors.append((futs[f], repr(e)))
                    print(f"[map] job {futs[f]} failed: {e!r}", flush=True)
                    continue
                if sink:
                    with lock:
                        append_jsonl(sink, out[futs[f]])
        if errors:
            raise RuntimeError(f"{len(errors)} of {len(out)} jobs failed (results of the others were saved): {errors[:3]}")
        return out

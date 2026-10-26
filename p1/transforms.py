"""Turns (§4.1), discretisation (§4.2) and prompt edits (§4.4, Stage 6). Pure functions, no model calls.

Every edit asserts how many times its span occurs, and tests/test_core.py checks each edit
against a fresh harness render, so an edited prompt is byte-identical to what the harness
would have produced for that listener.
"""
import json
import re

from p1.common import read_jsonl

NO_MSG = "- No messages received from other sellers in the previous hour.\n"
CATEGORIES = ("lower", "hold", "raise", "withdraw")


class EditError(ValueError):
    pass


# ---------------------------------------------------------------- discretisation
def to_ask(x):
    """Harness ask -> float, 'null' (withdraw), or None (malformed: JSON null, missing, non-numeric)."""
    if isinstance(x, str) and x.strip().lower() == "null":
        return "null"
    if isinstance(x, bool) or x is None:
        return None
    try:
        return float(str(x).replace("$", "").replace(",", "").strip())
    except ValueError:
        return None


def discretise(ask, prev, tau):
    """Category of `ask` relative to `prev` with threshold tau; None if malformed. Compared in cents."""
    a = to_ask(ask)
    if a is None:
        return None
    if a == "null":
        return "withdraw"
    d, t = round((a - prev) * 100), round(tau * 100)
    return "lower" if d < -t else "raise" if d > t else "hold"


def first_letter(s):
    m = re.search(r"[A-Za-z]", s or "")
    return m.group(0).upper() if m else None


# ---------------------------------------------------------------- span edits
def replace_once(prompt, old, new):
    n = prompt.count(old)
    if n != 1:
        raise EditError(f"expected exactly 1 match, found {n}: {old[:80]!r}")
    return prompt.replace(old, new)


def edit_spans(prompt, spans):
    """Apply [(old, new), ...], each required to match exactly once. O7 passes many spans."""
    for old, new in spans:
        prompt = replace_once(prompt, old, new)
    return prompt


def message_line(sender, msg):
    return f"\n- From {sender}: {msg}\n"


def edit_message(prompt, sender, old, new):
    """Replace `sender`'s received message; new=None renders the harness's 'no message' case exactly."""
    line = message_line(sender, old)
    if new is not None:
        return replace_once(prompt, line, message_line(sender, new))
    block = section(prompt, "# Messages Received from Other Sellers (Previous Hour)\n", "# Output Format\n")
    if block.count("\n- From ") > 1:           # other senders remain: drop the line
        return replace_once(prompt, line, "")
    return replace_once(prompt, "\n" + line + "\n", "\n" + NO_MSG)   # A was the only sender


def _delete_between(prompt, start, end, back=0):
    """Delete from `start` up to `back` chars before the next header `end` (the template's own literal
    newlines between the section and that header). 0 occurrences of start = section absent = no-op."""
    n = prompt.count(start)
    if n == 0:
        return prompt, 0
    if n != 1 or prompt.count(end) != 1:
        raise EditError(f"section delimiters not unique: {start!r} x{n}, {end!r} x{prompt.count(end)}")
    i, j = prompt.index(start), prompt.index(end) - back
    if j < i:
        raise EditError(f"{end!r} precedes {start!r}")
    return prompt[:i] + prompt[j:], 1


def delete_private_instruction(prompt, turn=None):
    return _delete_between(prompt, "# Private Instruction\n", "\n# Your Memory\n")


def delete_memory(prompt, turn=None):
    return _delete_between(prompt, "\n# Your Memory\n", "\n# Market Status\n", back=1)


def delete_scratchpad(prompt, turn=None):
    return _delete_between(prompt, "# Current Strategy Scratchpad\n", "\n# Output Format\n", back=1)


REFERENCE_LINE = "Your most recent ask was ${ask:.2f}."
REFERENCE_ANCHOR = "# Your Successful Trades So Far\n\n"


def add_reference_line(prompt, turn):
    """Post-hoc C0' (paper, Experiment #1): give the listener B's registered previous ask, a public fact,
    as one line directly under the 'Your Successful Trades So Far' heading. Exactly one insertion."""
    line = REFERENCE_LINE.format(ask=turn["prev_ask_B"])
    return replace_once(prompt, REFERENCE_ANCHOR, REFERENCE_ANCHOR + line + "\n"), 1


TRANSFORMS = {f.__name__: f for f in (delete_private_instruction, delete_memory, delete_scratchpad, add_reference_line)}


def apply_listener(prompt, transforms, turn=None):
    """Listener = (model, [transform names]). Returns (prompt, {transform: n_deleted})."""
    log = {}
    for name in transforms:
        prompt, log[name] = TRANSFORMS[name](prompt, turn)
    return prompt, log


def section(prompt, start, end):
    """Text of a section (for the D1 memory/scratchpad code-mention count); '' if absent."""
    if start not in prompt:
        return ""
    i = prompt.index(start) + len(start)
    return prompt[i:prompt.index(end, i)] if end in prompt[i:] else prompt[i:]


# ---------------------------------------------------------------- turns
def final_calls(calls):
    """(agent_id, round) -> (line_no, call) for the call whose parsed reply the harness acted on."""
    out = {}
    for i, c in enumerate(calls):
        if c["parsed"] is not None:
            out[(c["agent_id"], c["round"])] = (i, c)
    return out


def session_turns(session_dir, tau, max_len):
    """All turns of one session with eligibility (§4.1). Ineligible ones carry a reason."""
    S = json.loads((session_dir / "session.json").read_text())
    calls = read_jsonl(session_dir / "calls.jsonl")
    fin = final_calls(calls)
    A, B, sid = S["A_id"], S["B_id"], S["session_id"]
    turns = []
    for r in range(2, S["rounds"] + 1):
        t = {"turn_id": f"{sid}-r{r:02d}", "session_id": sid, "condition": S["condition"], "round": r,
             "A_id": A, "B_id": B}
        a, b = fin.get((A, r - 1)), fin.get((B, r))
        msg = a[1]["parsed"].get("message_to_sellers") if a else None
        prev = [to_ask(fin[(B, q)][1]["parsed"].get("ask")) for q in range(1, r) if (B, q) in fin]
        prev = [x for x in prev if isinstance(x, float)]
        reason = (None if a and b else "missing A or B call") or \
                 (None if msg else "A sent no message") or \
                 (None if isinstance(msg, str) else "non-string message") or \
                 (None if prev else "B has no previous non-null ask")
        if reason is None:
            z = msg[:max_len]  # harness truncates before broadcasting
            if b[1]["messages"][0]["content"].count(message_line(A, z)) != 1:
                reason = "z_t line not found exactly once in B's prompt"
        if reason:
            turns.append(dict(t, eligible=False, reason=reason))
            continue
        logged = b[1]["parsed"].get("ask")
        turns.append(dict(t, eligible=True, z_t=z, A_prompt_ref=f"{sid}:{a[0]}", B_prompt_ref=f"{sid}:{b[0]}",
                          prev_ask_B=prev[-1], logged_ask_B=logged, logged_cat_B=discretise(logged, prev[-1], tau)))
    return turns


def load_ref(runs_dir, ref, _cache={}):
    sid, line = ref.rsplit(":", 1)
    if sid not in _cache:
        _cache[sid] = read_jsonl(runs_dir / sid / "calls.jsonl")
    return _cache[sid][int(line)]

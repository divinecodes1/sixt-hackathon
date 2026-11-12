"""final_judge.py: team Divinecodes' judge for Project 3 "Judge the Judge".

Recipe (same code for every criterion; only --criterion, --policy and --dev change):

  prepare()  Deterministic, no LLM. Self-validates the generic code rules on the labelled examples and picks
             few-shot examples (one per edit type, alternating labels) with their construction notes as rationale.
  judge()    Stateless, at most 3 LLM calls per reply:
     rules   "number not in the reference policy" check. Enabled only if it never fires on a pass example;
             verdict mode if it also fires on at least one fail example, hint mode otherwise.
     call 1  Structured check (JSON): every claim of the reply is quoted, matched to its policy rule and compared
             in both directions: numbers, the conditions/limits the policy attaches (kept or dropped?), certainty
             level, scope. Then: does the claim violate the criterion? The verdict is computed in code.
     call 2  Only if call 1 found a candidate violation: a fresh-context verifier confirms or rejects each finding.
     call 3  Only if call 2 rejected everything: an independent holistic judgment with examples breaks the tie.

Environment (see .env.example): JUDGE_LLM_BASE_URL, JUDGE_LLM_API_KEY, JUDGE_LLM_MODEL (claude-haiku-4.5).
Optional: JUDGE_MAX_TOKENS (default 1600), JUDGE_LLM_TIMEOUT, JUDGE_LLM_MAX_RETRIES,
JUDGE_LLM_CACHE (development only; never set it for the scored runs: it would fake consistency).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import threading
import time
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import baseline_judge as _bj  # noqa: E402  (HTTP helpers and retry policy from the starter kit)

MAX_TOKENS = int(os.environ.get("JUDGE_MAX_TOKENS", "1600"))
MAX_EXAMPLES = 8

# ----------------------------------------------------------------------------------------------- state set in prepare()
# Read-only after prepare(); judge() never writes to these.
CONFIG: dict = {"criterion": "", "policy": "", "examples_text": "", "number_rule": "off", "policy_numbers": frozenset()}

# Diagnostics only (never influence a verdict): calls made, parse failures, model ids the endpoint reported.
STATS = {"calls": 0, "parse_failures": 0, "rule_fail": 0, "models": set()}
_lock = threading.Lock()
_cache: dict | None = None
unparsed = 0  # read by run_judge.py's end-of-run report


# ================================================================================================ LLM client
def _chat(system: str, user: str) -> str:
    """One chat completion at temperature 0. Retries on 429/5xx like the baseline client."""
    base = os.environ.get("JUDGE_LLM_BASE_URL", "").rstrip("/")
    key = os.environ.get("JUDGE_LLM_API_KEY", "")
    model = os.environ.get("JUDGE_LLM_MODEL", "")
    if not (base and key and model):
        raise _bj.LLMError("set JUDGE_LLM_BASE_URL, JUDGE_LLM_API_KEY and JUDGE_LLM_MODEL (see .env.example)")
    timeout = float(os.environ.get("JUDGE_LLM_TIMEOUT", "90"))
    payload = {"model": model, "temperature": 0, "max_tokens": MAX_TOKENS,
               "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}

    cache_path = os.environ.get("JUDGE_LLM_CACHE") or None
    ckey = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
    if cache_path:
        global _cache
        with _lock:
            if _cache is None:
                _cache = json.load(open(cache_path, encoding="utf-8")) if os.path.exists(cache_path) else {}
            if ckey in _cache:
                return _cache[ckey]

    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    for attempt in range(_bj.MAX_RETRIES + 1):
        try:
            body = _bj._post(f"{base}/chat/completions", payload, headers, timeout)
            choice = body["choices"][0]
            text = choice["message"]["content"] or ""
            with _lock:
                STATS["calls"] += 1
                STATS["models"].add(str(body.get("model", "?")))
            if choice.get("finish_reason") == "length":
                text += "\n<!-- truncated -->"
            break
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                raise _bj.LLMError(f"LLM endpoint refused the key (HTTP {e.code})")
            if e.code not in _bj._RETRY_STATUS or attempt == _bj.MAX_RETRIES:
                raise _bj.LLMError(f"LLM request failed with HTTP {e.code}") from e
            time.sleep(_bj._wait(attempt, e.headers.get("Retry-After") if e.headers else None))
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt == _bj.MAX_RETRIES:
                raise _bj.LLMError(f"LLM request failed: {e}") from e
            time.sleep(_bj._wait(attempt, None))

    if cache_path:
        with _lock:
            _cache[ckey] = text
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(_cache, f)
    return text


def _parse_json(text: str) -> dict | None:
    """The last JSON object in the answer, preferably inside <json>...</json>. None if there is none."""
    blocks = re.findall(r"<json>(.*?)</json>", text, flags=re.S)
    candidates = blocks[::-1] if blocks else [text]
    for c in candidates:
        c = c.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        start, end = c.find("{"), c.rfind("}")
        if start < 0 or end <= start:
            continue
        try:
            obj = json.loads(c[start:end + 1])
        except ValueError:
            continue
        if isinstance(obj, dict):
            return obj
    _note_parse_failure()
    return None


def _parse_verdict(text: str) -> str | None:
    hits = re.findall(r"<verdict>\s*(PASS|FAIL)\s*</verdict>", text, flags=re.I)
    if hits:
        return hits[-1].lower()
    words = re.findall(r"\b(PASS|FAIL)\b", text)
    if words:
        return words[-1].lower()
    _note_parse_failure()
    return None


def _note_parse_failure() -> None:
    global unparsed
    with _lock:
        STATS["parse_failures"] += 1
        unparsed += 1


# ================================================================================================ rule: numbers
_NUM = re.compile(r"(?<![\w.,])\d+(?:[.,]\d+)*")


def _to_number(tok: str) -> float | None:
    """'1.000,50' -> 1000.5, '1,000' -> 1000, '12,5' -> 12.5, '29' -> 29."""
    t = tok
    if "," in t and "." in t:
        dec = "," if t.rfind(",") > t.rfind(".") else "."
        t = t.replace("." if dec == "," else ",", "").replace(dec, ".")
    elif "," in t or "." in t:
        sep = "," if "," in t else "."
        head, _, tail = t.rpartition(sep)
        t = f"{head.replace(sep, '')}.{tail}" if len(tail) != 3 else t.replace(sep, "")
    try:
        return float(t)
    except ValueError:
        return None


def numbers_in(text: str) -> list[tuple[str, float]]:
    out = []
    for m in _NUM.finditer(text):
        v = _to_number(m.group(0))
        if v is not None:
            out.append((m.group(0), v))
    return out


def unknown_numbers(reply: str, policy_numbers: frozenset) -> list[str]:
    """Numbers in the reply that appear nowhere in the reference policy."""
    return [tok for tok, v in numbers_in(reply) if v not in policy_numbers]


# ================================================================================================ prepare()
def _label(case: dict, side: str) -> str:
    if side == "original":
        return str(case.get("original_label", "pass")).lower()
    return str(case.get("edited_label", "fail" if case.get("edit_family") == "harmful" else "pass")).lower()


def _labelled_replies(dev_pairs: list[dict]) -> list[tuple[str, str]]:
    """Distinct (reply, label) from the labelled pairs: originals and edited replies."""
    seen, out = set(), []
    for c in dev_pairs:
        for side, text in (("original", c.get("original")), ("edited", c.get("edited"))):
            if text and text not in seen:
                seen.add(text)
                out.append((text, _label(c, side)))
    return out


def _validate_number_rule(policy_numbers: frozenset, dev_pairs: list[dict]) -> str:
    """off: fires on a pass example (or no examples); verdict: fires only on fail examples; hint: never fires."""
    labelled = _labelled_replies(dev_pairs)
    if not labelled:
        return "hint"
    fires = [(lab, bool(unknown_numbers(text, policy_numbers))) for text, lab in labelled]
    if any(f and lab == "pass" for lab, f in fires):
        return "off"
    return "verdict" if any(f and lab == "fail" for lab, f in fires) else "hint"


def _pick_examples(dev_pairs: list[dict]) -> list[dict]:
    """One harmful and one harmless example per edit type, deterministic, alternating labels, at most MAX_EXAMPLES."""
    by_type: dict[str, list[dict]] = {}
    for c in sorted(dev_pairs, key=lambda c: str(c.get("case_id"))):
        by_type.setdefault(str(c.get("edit_type", "?")), []).append(c)
    fails, passes = [], []
    for t in sorted(by_type):
        cs = by_type[t]
        # prefer an English example, then the shortest reply: cheap to read and clear to learn from
        c = sorted(cs, key=lambda c: (c.get("lang") != "en", len(c.get("edited", ""))))[0]
        item = {"question": c.get("question", ""), "lang": c.get("lang", ""), "reply": c.get("edited", ""),
                "label": _label(c, "edited").upper(), "note": c.get("edit_note") or ""}
        (fails if item["label"] == "FAIL" else passes).append(item)
    out = []
    while (fails or passes) and len(out) < MAX_EXAMPLES:
        for pool in (fails, passes):
            if pool and len(out) < MAX_EXAMPLES:
                out.append(pool.pop(0))
    return out


def _format_examples(examples: list[dict]) -> str:
    parts = []
    for i, e in enumerate(examples, 1):
        why = e["note"]
        why = (f"A labeller marked this {e['label']}. Construction note (what was changed from a correct reply): {why}"
               if why else f"A labeller marked this {e['label']}.")
        parts.append(f'<example id="{i}">\n<question>{e["question"]}</question>\n'
                     f'<reply lang="{e["lang"]}">{e["reply"]}</reply>\n<label>{e["label"]}</label>\n'
                     f"<why>{why}</why>\n</example>")
    return "\n".join(parts)


def prepare(criterion: str, policy: str, dev_pairs: list[dict]) -> None:
    policy_numbers = frozenset(v for _, v in numbers_in(policy))
    CONFIG.update(
        criterion=criterion.strip(),
        policy=policy.strip(),
        policy_numbers=policy_numbers,
        number_rule=_validate_number_rule(policy_numbers, dev_pairs),
        examples_text=_format_examples(_pick_examples(dev_pairs)),
    )
    print(f"final_judge: number rule = {CONFIG['number_rule']}, "
          f"{CONFIG['examples_text'].count('<example ')} examples", file=sys.stderr)


# ================================================================================================ prompts
SYSTEM_CHECK = """You are a meticulous reviewer. You check ONE customer-service reply against a written criterion, \
using a reference policy as the only source of truth. You work claim by claim, quote exactly, reason briefly in \
English (the reply may be in English, German, French, Spanish or Italian) and answer with one JSON object inside \
<json></json> tags and nothing else."""

CHECK_INSTRUCTIONS = """Check the reply in <reply> against the criterion, using the policy as reference.

Step 1. Split the reply into its claims: every sentence or clause that states a fact, number, fee, time limit, \
entitlement, possibility, condition or promise. Greetings, thanks and general reassurance with no specific \
commitment are not claims unless the criterion is about them.

Step 2. For each claim, compare it with the policy rule it is about, in BOTH directions:
- "policy_rule": quote the relevant policy text, or null if the policy says nothing about it.
- "number_vs_policy": "same", "more_favourable_to_customer", "less_favourable_to_customer", "not_in_policy" or "no_number".
- "policy_conditions": every condition, limit, exception or qualifier the policy attaches to this rule \
(e.g. "only if ...", "subject to ...", "some branches", "up to ..."). For each one, "status" is:
   "kept" if the reply states it anywhere (any wording, any sentence, any language);
   "dropped" if the reply states the claim but leaves the condition out;
   "not_applicable" if the reply does not make the part of the claim the condition qualifies.
- "certainty_policy" and "certainty_reply": how certain the statement is, 0 = may / can / possible / some, \
1 = often / usually / most / normally, 2 = generally / as a rule, 3 = always / will / guaranteed / all / any. \
Translate the reply's wording to this scale (e.g. "in der Regel", "généralement", "di solito", "normalmente").
- "scope": "same", "wider" (applies to more cases, products, branches or people than the policy), "narrower" or "n/a".
- "violates_criterion": true or false, with a one-sentence "reason". Decide this ONLY by what the criterion asks. \
Greeting, filler, sentence order, length, politeness, register and language matter only if the criterion is about \
them. Being stricter or less generous than the policy, or saying less, is not a violation unless the criterion says so.

Step 3. "verdict": "FAIL" if any claim violates the criterion, else "PASS".

Answer format:
<json>{"claims": [{"quote": "...", "gloss_en": "...", "policy_rule": "...", "number_vs_policy": "...",
"policy_conditions": [{"condition": "...", "status": "..."}], "certainty_policy": 0, "certainty_reply": 0,
"scope": "...", "violates_criterion": false, "reason": "..."}], "verdict": "PASS"}</json>"""

SYSTEM_VERIFY = """You double-check findings of another reviewer about ONE customer-service reply. Be precise and \
independent: the other reviewer is wrong fairly often in both directions. Answer with one JSON object inside \
<json></json> tags and nothing else."""

VERIFY_INSTRUCTIONS = """Another reviewer says the reply violates the criterion at the points listed in <findings>.
For each finding, re-read the whole reply and the policy and decide:
- "confirmed": the reply really violates the criterion there;
- "rejected": it does not (for example the condition is stated elsewhere in the reply in other words, the number \
matches the policy, or the difference does not matter for this criterion).
Keep in mind: leaving out a condition, limit or hedge that the policy attaches, while still stating the entitlement, \
makes the statement stronger than the policy. That is a real change of meaning, not brevity. Greeting, filler, \
sentence order, length, politeness and language matter only if the criterion is about them.

Answer format:
<json>{"findings": [{"id": 1, "decision": "confirmed", "reason": "..."}]}</json>"""

SYSTEM_HOLISTIC = """You review a customer-service reply before it is sent. You compare it carefully with the \
reference policy and decide whether it meets the criterion."""

HOLISTIC_INSTRUCTIONS = """Decide whether the reply in <reply> violates the criterion. Compare each statement with \
the policy: numbers, every condition or limit the policy attaches, how certain the statement is, and its scope. \
Judge only what the criterion asks about; greeting, filler, sentence order, length and language matter only if the \
criterion is about them. Write at most three short sentences of reasoning in English, then \
<verdict>PASS</verdict> or <verdict>FAIL</verdict>."""


def _context(question: str, reply: str, lang: str, with_examples: bool) -> str:
    parts = [f"<policy>\n{CONFIG['policy']}\n</policy>", f"<criterion>\n{CONFIG['criterion']}\n</criterion>"]
    if with_examples and CONFIG["examples_text"]:
        parts.append("<examples>\nLabelled replies to other questions, for calibration:\n"
                     f"{CONFIG['examples_text']}\n</examples>")
    parts.append(f"<question>{question}</question>")
    parts.append(f'<reply lang="{lang}">{reply}</reply>')
    return "\n\n".join(parts)


# ================================================================================================ aggregation in code
def _findings(check: dict, rule_numbers: list[str]) -> list[dict]:
    """Candidate violations from call 1: claims marked as violating the criterion."""
    out = []
    for c in check.get("claims") or []:
        if isinstance(c, dict) and c.get("violates_criterion") is True:
            out.append({"quote": str(c.get("quote", "")), "reason": str(c.get("reason", "")),
                        "policy_rule": c.get("policy_rule")})
    if not out and str(check.get("verdict", "")).upper() == "FAIL":
        out.append({"quote": "(whole reply)", "reason": "overall verdict FAIL", "policy_rule": None})
    return out


def _rule_overturned(check: dict | None, rule_numbers: list[str]) -> bool:
    """True if call 1 explicitly found every flagged number consistent with or stricter than the policy."""
    if not check:
        return False
    for tok in rule_numbers:
        ok = False
        for c in check.get("claims") or []:
            if isinstance(c, dict) and tok in str(c.get("quote", "")):
                ok = c.get("number_vs_policy") in ("same", "less_favourable_to_customer") \
                     and c.get("violates_criterion") is False
                break
        if not ok:
            return False
    return True


# ================================================================================================ judge()
def judge(question: str, reply: str, lang: str, criterion: str, policy: str) -> str:
    if not CONFIG["criterion"]:  # run without prepare(): still works, without examples or rule
        prepare(criterion, policy, [])
    rule_numbers = [] if CONFIG["number_rule"] == "off" else unknown_numbers(reply, CONFIG["policy_numbers"])

    # ---- call 1: structured, claim-by-claim check
    user = _context(question, reply, lang, with_examples=True)
    if rule_numbers:
        user += ("\n\n<code_check>Numbers in the reply that do not appear in the policy: "
                 + ", ".join(rule_numbers) + ". Check them carefully.</code_check>")
    check = _parse_json(_chat(SYSTEM_CHECK, user + "\n\n" + CHECK_INSTRUCTIONS))

    if rule_numbers and CONFIG["number_rule"] == "verdict" and not _rule_overturned(check, rule_numbers):
        with _lock:
            STATS["rule_fail"] += 1
        return "fail"

    if check is None:  # unparseable: let the holistic judgment decide (deterministic fallback)
        return _holistic(question, reply, lang) or "fail"
    findings = _findings(check, rule_numbers)
    if not findings:
        return "pass"

    # ---- call 2: fresh-context verification of the candidate violations only
    listed = "\n".join(f'{i}. quote: "{f["quote"]}" | reviewer\'s reason: {f["reason"]}'
                       for i, f in enumerate(findings, 1))
    user2 = _context(question, reply, lang, with_examples=False) + f"\n\n<findings>\n{listed}\n</findings>"
    verify = _parse_json(_chat(SYSTEM_VERIFY, user2 + "\n\n" + VERIFY_INSTRUCTIONS))
    decisions = [str(d.get("decision", "")).lower() for d in (verify or {}).get("findings") or [] if isinstance(d, dict)]
    if any(d == "confirmed" for d in decisions):
        return "fail"

    # ---- call 3: call 1 and call 2 disagree (or call 2 unreadable): independent holistic tiebreak
    return _holistic(question, reply, lang) or "fail"


def _holistic(question: str, reply: str, lang: str) -> str | None:
    user = _context(question, reply, lang, with_examples=True) + "\n\n" + HOLISTIC_INSTRUCTIONS
    return _parse_verdict(_chat(SYSTEM_HOLISTIC, user))

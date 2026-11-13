"""final_judge.py: team Divinecodes' judge for Project 3 "Judge the Judge".

Recipe (same code for every criterion; only --criterion, --policy and --dev change):

  prepare()  Deterministic, no LLM. Self-validates the generic code rules on the labelled examples and picks
             few-shot examples (one per edit type, alternating labels) with their construction notes as rationale.
  judge()    Stateless, at most 3 LLM calls per reply:
     rules   "number not in the reference policy" check. Enabled only if it never fires on a pass example;
             verdict mode if it also fires on at least one fail example, hint mode otherwise.
     call 1  Structured check (JSON): every claim of the reply is quoted, matched to its policy rule and compared
             in both directions: numbers, the conditions/limits the policy attaches (kept or dropped?), certainty
             level, scope. Then: does the claim violate the criterion? Code aggregates the per-claim booleans.
     call 2  Only if call 1 found a candidate violation: a fresh-context verifier confirms or rejects each finding.
             (VERIFY_WITNESS, on since 12:25: a confirm counts only with the reply's exact words + a concrete case.)
             (SECOND_LOOK, off by default: also when call 1 passed but its own fields record a policy difference.)
     call 3  Only if calls 1 and 2 disagree: a holistic judgment with examples breaks the tie (ADJUDICATE, off by
             default: it sees both reviewers' arguments).
Design document: ../docs/ARCHITECTURE.md

Environment (see .env.example): JUDGE_LLM_BASE_URL, JUDGE_LLM_API_KEY, JUDGE_LLM_MODEL (claude-haiku-4.5).
Optional: JUDGE_MAX_TOKENS (default 3000), JUDGE_TRACE (path: one JSON line per reply with the decision path), JUDGE_LLM_TIMEOUT, JUDGE_LLM_MAX_RETRIES,
JUDGE_TRACE_REASONS=1 (add call-1 findings and call-2 decisions to the trace: contains reply quotes, dev only),
JUDGE_LLM_OMIT_TEMPERATURE=1 (never send temperature; without it, a 400 that rejects temperature is resent without it),
JUDGE_LLM_CACHE (development only; never set it for the scored runs: it would fake consistency).
"""
from __future__ import annotations

import difflib
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

MAX_TOKENS = int(os.environ.get("JUDGE_MAX_TOKENS", "3000"))  # room for long JSON; unused tokens cost nothing
MAX_EXAMPLES = 8

# ------------------------------------------------------------------------------------------------ recipe settings
# Generic inference-time settings, none of them criterion-specific. The defaults are the judge's behaviour;
# ../dev_tools/experiments.py measures other values on temporary copies of this file. Fixed before the freeze.
NUMBER_RULE_MAX = "verdict"  # strongest mode prepare() may give the code rule: "verdict" or "hint"
EXAMPLE_STYLE = "single"     # "single": the labelled reply alone; "contrast": its correct original shown next to it
PREFILL = False              # start the model's JSON answer with "<json>" (Haiku 4.5 supports prefill): no preamble
THINKING_BUDGET = 0          # > 0: extended thinking on call 1 with this token budget (needs temperature 1)
SECOND_LOOK = False          # call 1 passes but its own fields show a difference from the policy: call 2 checks it
ADJUDICATE = False           # call 3 sees both reviewers' arguments instead of judging from scratch
CONDITION_EVIDENCE = False   # a condition marked "kept" must quote the reply; code checks the quote, else call 2 checks
CLAUSE_IDS = False           # policy split into numbered clauses (no LLM); call 1 cites id + exact words, code checks
HEDGE_FROM_QUOTE = False     # certainty rated from the original words (hedge words copied), quantities go to scope
VERIFY_DEANCHOR = False      # call 2 gets only where to look (quote, policy text), not the first reviewer's conclusion
VERIFY_EXAMPLES = False      # call 2 also sees the labelled examples (calibration against false confirms on good replies)
VERIFY_SCOPED = False        # call 2: a limitation stated anywhere counts; a condition matters only for the promise it limits
VERIFY_WITNESS = True        # call 2 confirms only with the reply's exact words + a concrete case; code checks the quote
TRUST_VERIFY_REJECT = True   # call 2 read the findings and confirmed none: pass, no call 3 (call 3 only if unreadable)
HEDGE_NOT_CONDITION = False  # call 2: a certainty word ("often") does not state a dropped condition ("subject to ...")

# ----------------------------------------------------------------------------------------------- state set in prepare()
# Read-only after prepare(); judge() never writes to these.
CONFIG: dict = {"criterion": "", "policy": "", "examples_text": "", "number_rule": "off", "policy_numbers": frozenset(),
                "clauses": {}, "policy_numbered": ""}

# Diagnostics only (never influence a verdict): calls made, parse failures, model ids the endpoint reported.
STATS = {"calls": 0, "parse_failures": 0, "rule_fail": 0, "truncated": 0, "temperature_dropped": 0, "models": set()}
_lock = threading.Lock()
_cache: dict | None = None
unparsed = 0  # read by run_judge.py's end-of-run report


# ================================================================================================ LLM client
def _chat(system: str, user: str, prefill: str = "", thinking: int = 0) -> str:
    """One chat completion at temperature 0. Retries on 429/5xx like the baseline client.

    prefill: the start of the answer, sent as a final assistant message and put back in front of the returned text.
    thinking: extended-thinking budget in tokens; the API then requires the default temperature, and no prefill."""
    base = os.environ.get("JUDGE_LLM_BASE_URL", "").rstrip("/")
    key = os.environ.get("JUDGE_LLM_API_KEY", "")
    model = os.environ.get("JUDGE_LLM_MODEL", "")
    if not (base and key and model):
        raise _bj.LLMError("set JUDGE_LLM_BASE_URL, JUDGE_LLM_API_KEY and JUDGE_LLM_MODEL (see .env.example)")
    timeout = float(os.environ.get("JUDGE_LLM_TIMEOUT", "90"))
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    if thinking:
        prefill = ""
        payload = {"model": model, "max_tokens": MAX_TOKENS + thinking, "messages": messages,
                   "thinking": {"type": "enabled", "budget_tokens": thinking}}
    else:
        if prefill:
            messages.append({"role": "assistant", "content": prefill})
        payload = {"model": model, "temperature": 0, "max_tokens": MAX_TOKENS, "messages": messages}

    cache_path = os.environ.get("JUDGE_LLM_CACHE") or None
    ckey = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
    if cache_path:
        global _cache
        with _lock:
            if _cache is None:
                _cache = json.load(open(cache_path, encoding="utf-8")) if os.path.exists(cache_path) else {}
            if ckey in _cache:
                return _cache[ckey]

    if "temperature" in payload and os.environ.get("JUDGE_LLM_OMIT_TEMPERATURE", "") not in ("", "0"):
        del payload["temperature"]  # gateway known to reject the parameter (see _temperature_rejected)
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    attempt = 0
    while True:
        try:
            body = _bj._post(f"{base}/chat/completions", payload, headers, timeout)
            choice = body["choices"][0]
            text = choice["message"]["content"] or ""
            with _lock:
                STATS["calls"] += 1
                STATS["models"].add(str(body.get("model", "?")))
            if choice.get("finish_reason") == "length":
                text += "\n<!-- truncated -->"
                with _lock:
                    STATS["truncated"] += 1
            if prefill and not text.lstrip().startswith(prefill):
                text = prefill + text
            break
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                raise _bj.LLMError(f"LLM endpoint refused the key (HTTP {e.code})")
            if "temperature" in payload and _temperature_rejected(e):
                # Newer Anthropic API versions reject `temperature` with HTTP 400. Resend the same request without
                # it (the model's default sampling). Not an LLM call: the rejected request produced no answer.
                del payload["temperature"]
                with _lock:
                    STATS["temperature_dropped"] += 1
                continue
            if e.code not in _RETRY_STATUS or attempt >= _bj.MAX_RETRIES:
                raise _bj.LLMError(f"LLM request failed with HTTP {e.code}") from e
            time.sleep(_bj._wait(attempt, e.headers.get("Retry-After") if e.headers else None))
            attempt += 1
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt >= _bj.MAX_RETRIES:
                raise _bj.LLMError(f"LLM request failed: {e}") from e
            time.sleep(_bj._wait(attempt, None))
            attempt += 1

    if cache_path:
        with _lock:
            _cache[ckey] = text
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(_cache, f)
    return text


_RETRY_STATUS = _bj._RETRY_STATUS | {408, 529}  # + request timeout and Anthropic's "overloaded"


def _temperature_rejected(e: urllib.error.HTTPError) -> bool:
    """HTTP 400 whose error text names the temperature parameter (e.g. Anthropic API version 2026-10-21)."""
    if e.code != 400:
        return False
    try:
        detail = e.read().decode("utf-8", "replace")
    except Exception:
        return False
    return "temperature" in detail.lower()


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
    """One example (the edited reply) per edit type, English and shortest first, deterministic, at most MAX_EXAMPLES,
    ordered fail/pass alternately. Labels are balanced only as far as the types allow: with a single type (no
    edit_type given) the shortest replies are taken regardless of label."""
    by_type: dict[str, list[dict]] = {}
    for c in sorted(dev_pairs, key=lambda c: str(c.get("case_id"))):
        by_type.setdefault(str(c.get("edit_type", "?")), []).append(c)
    # prefer an English example, then the shortest reply: cheap to read and clear to learn from
    ranked = {t: sorted(cs, key=lambda c: (c.get("lang") != "en", len(c.get("edited", "")))) for t, cs in by_type.items()}
    chosen: list[dict] = []
    for rnd in range(max((len(v) for v in ranked.values()), default=0)):
        # one per type first; more rounds only when there are fewer types than examples (e.g. no edit_type given)
        chosen += [ranked[t][rnd] for t in sorted(ranked) if rnd < len(ranked[t])]
        if len(chosen) >= MAX_EXAMPLES:
            break
    fails, passes = [], []
    for c in chosen:
        item = {"question": c.get("question", ""), "lang": c.get("lang", ""), "reply": c.get("edited", ""),
                "label": _label(c, "edited").upper(), "note": c.get("edit_note") or "",
                "original": c.get("original") or "", "orig_lang": c.get("orig_lang") or c.get("lang", ""),
                "orig_label": _label(c, "original").upper()}
        (fails if item["label"] == "FAIL" else passes).append(item)
    out = []
    while (fails or passes) and len(out) < MAX_EXAMPLES:
        for pool in (fails, passes):
            if pool and len(out) < MAX_EXAMPLES:
                out.append(pool.pop(0))
    return out


def _format_examples(examples: list[dict]) -> str:
    if EXAMPLE_STYLE == "contrast":
        return _format_contrast(examples)
    parts = []
    for i, e in enumerate(examples, 1):
        why = e["note"]
        why = (f"A labeller marked this {e['label']}. Construction note (what was changed from a correct reply): {why}"
               if why else f"A labeller marked this {e['label']}.")
        parts.append(f'<example id="{i}">\n<question>{e["question"]}</question>\n'
                     f'<reply lang="{e["lang"]}">{e["reply"]}</reply>\n<label>{e["label"]}</label>\n'
                     f"<why>{why}</why>\n</example>")
    return "\n".join(parts)


def _format_contrast(examples: list[dict]) -> str:
    """Each example as a minimal pair: a reply and a near-identical labelled variant, so the boundary is visible."""
    parts = []
    for i, e in enumerate(examples, 1):
        if not e["original"] or e["original"] == e["reply"]:
            parts.append(f'<example id="{i}">\n<question>{e["question"]}</question>\n'
                         f'<reply lang="{e["lang"]}">{e["reply"]}</reply>\n<label>{e["label"]}</label>\n</example>')
            continue
        why = f"<why>What differs from reply A: {e['note']}</why>\n" if e["note"] else ""
        parts.append(f'<example id="{i}">\n<question>{e["question"]}</question>\n'
                     f'<reply_a lang="{e["orig_lang"]}">{e["original"]}</reply_a>\n<label_a>{e["orig_label"]}</label_a>\n'
                     f'<reply_b lang="{e["lang"]}">{e["reply"]}</reply_b>\n<label_b>{e["label"]}</label_b>\n'
                     f"{why}</example>")
    return "\n".join(parts)


_TABLE_SEP = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")


def split_clauses(policy: str) -> dict[str, str]:
    """Deterministic, format-generic split of a policy into numbered clauses: each table row, list item or paragraph
    line is one clause, prefixed with its section heading. Table header rows and separators are skipped."""
    lines = policy.splitlines()
    clauses, section = {}, ""
    for i, raw in enumerate(lines):
        line = raw.strip()
        if not line or _TABLE_SEP.match(line):
            continue
        if line.startswith("#"):
            section = line.lstrip("#").strip()
            continue
        if i + 1 < len(lines) and _TABLE_SEP.match(lines[i + 1].strip()):
            continue  # table header row
        if line.startswith("|"):
            line = " | ".join(c.strip() for c in line.strip("|").split("|") if c.strip())
        line = re.sub(r"^[-*+]\s+|^\d+[.)]\s+", "", line)
        clauses[f"C{len(clauses) + 1}"] = f"{section}: {line}" if section else line
    return clauses


def prepare(criterion: str, policy: str, dev_pairs: list[dict]) -> None:
    policy_numbers = frozenset(v for _, v in numbers_in(policy))
    mode = _validate_number_rule(policy_numbers, dev_pairs)
    if mode == "verdict" and NUMBER_RULE_MAX == "hint":
        mode = "hint"
    clauses = split_clauses(policy)
    CONFIG.update(
        criterion=criterion.strip(),
        policy=policy.strip(),
        policy_numbers=policy_numbers,
        number_rule=mode,
        examples_text=_format_examples(_pick_examples(dev_pairs)),
        clauses=clauses,
        policy_numbered="\n".join(f"[{k}] {v}" for k, v in clauses.items()),
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


def _sub(text: str, old: str, new: str) -> str:
    if old not in text:
        raise AssertionError(f"prompt fragment not found: {old[:60]!r}")
    return text.replace(old, new, 1)


def _check_instructions() -> str:
    """CHECK_INSTRUCTIONS with the enabled schema switches applied (all off: the text is unchanged)."""
    s = CHECK_INSTRUCTIONS
    if CLAUSE_IDS:
        s = _sub(s, '- "policy_rule": quote the relevant policy text, or null if the policy says nothing about it.',
                 '- "clause_id": the id of the policy clause the claim is about (e.g. "C7"), or null if no clause '
                 'covers it.\n- "policy_rule": copy the relevant words of that clause exactly, or null.')
        s = _sub(s, '"policy_rule": "...",', '"clause_id": "C1", "policy_rule": "...",')
    if CONDITION_EVIDENCE:
        s = _sub(s, '   "kept" if the reply states it anywhere (any wording, any sentence, any language);',
                 '   "kept" if the reply states it anywhere (any wording, any sentence, any language); then "evidence" '
                 'must copy the exact words of the reply that state it (empty "evidence" means you found none);')
        s = _sub(s, '{"condition": "...", "status": "..."}', '{"condition": "...", "status": "...", "evidence": "..."}')
    if HEDGE_FROM_QUOTE:
        s = _sub(s, '- "certainty_policy" and "certainty_reply": how certain the statement is, 0 = may / can / possible / some, '
                 '1 = often / usually / most / normally, 2 = generally / as a rule, 3 = always / will / guaranteed / all / any. '
                 'Translate the reply\'s wording to this scale (e.g. "in der Regel", "généralement", "di solito", "normalmente").',
                 '- "hedge_words_policy" and "hedge_words_reply": copy exactly the words that express how certain or how '
                 'conditional the statement is (e.g. "usually", "in der Regel", "peut", "di solito", "siempre"), from the '
                 'policy and from the reply in its own language; [] if there are none.\n'
                 '- "certainty_policy" and "certainty_reply": rate those copied words, not a translation or summary: '
                 '0 = may / can / possible, 1 = often / usually / normally, 2 = generally / as a rule, '
                 '3 = always / will / guaranteed / no hedge at all. Words about quantity (some, most, all, any, every) '
                 'are not certainty: record them under "scope".')
        s = _sub(s, '{"quote": "...", "gloss_en": "...", ', '{"quote": "...", ')
        s = _sub(s, '"certainty_policy": 0, "certainty_reply": 0,',
                 '"hedge_words_policy": [], "hedge_words_reply": [], "certainty_policy": 0, "certainty_reply": 0,')
        s = _sub(s, '"violates_criterion": false, "reason": "..."}', '"gloss_en": "...", "violates_criterion": false, '
                 '"reason": "..."}')
    return s


def _context(question: str, reply: str, lang: str, with_examples: bool) -> str:
    policy = CONFIG["policy_numbered"] if CLAUSE_IDS and CONFIG["policy_numbered"] else CONFIG["policy"]
    parts = [f"<policy>\n{policy}\n</policy>", f"<criterion>\n{CONFIG['criterion']}\n</criterion>"]
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


def _norm(text: str) -> str:
    text = text.casefold().replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    text = text.replace("«", '"').replace("»", '"').replace("„", '"')
    text = re.sub(r"[*_`]+", "", text)  # markdown emphasis in the policy; models rarely copy it
    return re.sub(r"\s+", " ", text).strip(" .,;:!?\"'")


def quote_found(quote: str, source: str, min_cover: float = 0.85) -> bool:
    """True if the quote occurs in the source: exactly after normalising case, quotes and spaces, or as one
    contiguous block covering at least min_cover of the quote (tolerates small copying slips)."""
    q, src = _norm(str(quote or "")), _norm(source)
    if len(q) < 3:
        return False
    if q in src:
        return True
    m = difflib.SequenceMatcher(None, q, src, autojunk=False).find_longest_match(0, len(q), 0, len(src))
    return m.size >= min_cover * len(q)


def _evidence_findings(check: dict, reply: str) -> list[dict]:
    """Code-side checks of call 1's evidence (CONDITION_EVIDENCE, CLAUSE_IDS), only on claims call 1 did not already
    mark as violating. Each finding asks call 2 to look; none is a verdict by itself."""
    out = []
    for c in check.get("claims") or []:
        if not isinstance(c, dict) or c.get("violates_criterion") is True:
            continue
        quote, rule = str(c.get("quote", "")), c.get("policy_rule")
        if CONDITION_EVIDENCE:
            for d in c.get("policy_conditions") or []:
                if (isinstance(d, dict) and str(d.get("status", "")).lower() == "kept"
                        and not quote_found(d.get("evidence", ""), reply)):
                    out.append({"quote": quote, "policy_rule": rule, "source": "code",
                                "reason": f'the policy attaches "{d.get("condition", "")}"; it was marked as stated, '
                                          "but no words of the reply stating it were found",
                                "look_for": f'does the reply state the policy condition "{d.get("condition", "")}"?'})
        if CLAUSE_IDS and rule:
            cid = str(c.get("clause_id") or "")
            clause = CONFIG["clauses"].get(cid, "")
            if not quote_found(str(rule), clause):
                where = f"clause {cid}" if clause else "the policy"
                out.append({"quote": quote, "policy_rule": rule, "source": "code",
                            "reason": f"the policy text cited for this claim was not found in {where}",
                            "look_for": "which policy clause is this claim really about, and does it allow the claim?"})
    return out


def _rule_overturned(check: dict | None, rule_numbers: list[str]) -> bool:
    """True if call 1 explicitly found every flagged number consistent with or stricter than the policy."""
    if not check:
        return False
    claims = [c for c in check.get("claims") or [] if isinstance(c, dict)]
    for tok in rule_numbers:
        value = _to_number(tok)
        carrying = [c for c in claims if value in {v for _, v in numbers_in(str(c.get("quote", "")))}]
        if not carrying or not all(c.get("number_vs_policy") in ("same", "less_favourable_to_customer")
                                   and c.get("violates_criterion") is False for c in carrying):
            return False
    return True


def _differences(check: dict) -> list[dict]:
    """Claims call 1 did NOT mark as violating although its own fields record a difference from the policy.

    Symmetric on purpose (looser AND stricter), so nothing assumes which direction the criterion cares about:
    the verifier decides under the criterion text whether a difference matters."""
    out = []
    for c in check.get("claims") or []:
        if not isinstance(c, dict) or c.get("violates_criterion") is True:
            continue
        notes = [f'the policy attaches "{d.get("condition", "")}", which the reply leaves out'
                 for d in c.get("policy_conditions") or []
                 if isinstance(d, dict) and str(d.get("status", "")).lower() == "dropped"]
        cp, cr = c.get("certainty_policy"), c.get("certainty_reply")
        if isinstance(cp, (int, float)) and isinstance(cr, (int, float)) and cp != cr:
            notes.append(f"stated {'more' if cr > cp else 'less'} certainly than the policy ({cr} vs {cp}, scale 0-3)")
        if str(c.get("scope", "")).lower() in ("wider", "narrower"):
            notes.append(f"scope is {str(c.get('scope')).lower()} than the policy")
        if c.get("number_vs_policy") in ("more_favourable_to_customer", "less_favourable_to_customer", "not_in_policy"):
            notes.append(f"number: {c.get('number_vs_policy')}")
        if notes:
            out.append({"quote": str(c.get("quote", "")), "reason": "; ".join(notes), "policy_rule": c.get("policy_rule")})
    return out


SECOND_LOOK_INSTRUCTIONS = """A first reviewer compared the reply with the policy and noted the differences listed in \
<findings>, but did not count them as violations of the criterion. For each one, re-read the whole reply and the \
policy and decide:
- "confirmed": under the criterion, this difference makes the reply violate it;
- "rejected": it does not (the difference does not matter for this criterion, or the reviewer misread the reply, \
for example the condition is stated elsewhere in other words).
Keep in mind: leaving out a condition, limit or hedge that the policy attaches, while still stating the entitlement, \
makes the statement stronger than the policy. Saying less, or being stricter, is a different kind of change. \
Greeting, filler, sentence order, length, politeness and language matter only if the criterion is about them.

Answer format:
<json>{"findings": [{"id": 1, "decision": "rejected", "reason": "..."}]}</json>"""


def _trace(t: dict, path: str, verdict: str) -> str:
    """Optional audit log (JUDGE_TRACE): one JSON line per reply. Write-only: never read back, never affects a verdict."""
    path_file = os.environ.get("JUDGE_TRACE")
    if path_file:
        t.update(path=path, verdict=verdict)
        with _lock, open(path_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(t, ensure_ascii=False) + "\n")
    return verdict


def _ask(t: dict, system: str, user: str, **kw) -> str:
    t["calls"] += 1
    return _chat(system, user, **kw)


def _listed(findings: list[dict]) -> str:
    return "\n".join(f'{i}. quote: "{f["quote"]}" | reviewer\'s reason: {f["reason"]}' for i, f in enumerate(findings, 1))


def _listed_neutral(findings: list[dict]) -> str:
    """VERIFY_DEANCHOR: where to look, without anyone's conclusion."""
    rows = []
    for i, f in enumerate(findings, 1):
        row = f'{i}. passage: "{f["quote"]}" | policy text: {f.get("policy_rule") or "(find it yourself)"}'
        if f.get("look_for"):
            row += f" | question: {f['look_for']}"
        rows.append(row)
    return "\n".join(rows)


SYSTEM_VERIFY_NEUTRAL = """You check specific passages of ONE customer-service reply against a written criterion, \
using a reference policy as the only source of truth. Be precise and decide for yourself. Answer with one JSON object \
inside <json></json> tags and nothing else."""

VERIFY_NEUTRAL_INSTRUCTIONS = """The passages of the reply listed in <findings> need a careful check. For each one, \
re-read the whole reply and the policy, copy the policy words that govern it into "policy_quote", and decide:
- "violation": the reply violates the criterion at this point;
- "no_violation": it does not.
Keep in mind: leaving out a condition, limit or hedge that the policy attaches, while still stating the entitlement, \
makes the statement stronger than the policy. That is a real change of meaning, not brevity. A condition stated \
anywhere in the reply, in any words or language, counts as stated. Greeting, filler, sentence order, length, \
politeness and language matter only if the criterion is about them.

Answer format:
<json>{"findings": [{"id": 1, "policy_quote": "...", "decision": "no_violation", "reason": "..."}]}</json>"""


VERIFY_WITNESS_INSTRUCTIONS = """Another reviewer says the reply violates the criterion at the points listed in \
<findings>. That reviewer raises many false alarms on correct replies, so check each finding yourself. Re-read the \
whole reply and the policy and decide:
- "confirmed" only if you can do both: copy into "reply_words" the exact words of the reply (in its own language) \
that violate the criterion, and describe in "situation" one concrete case, consistent with the policy, in which a \
reader who trusts exactly those words would be misled about something the criterion cares about;
- "rejected" otherwise: for example the point is stated elsewhere in the reply in other words, the reply's own \
wording ("try", "often", "most", "can", "may" or similar) already leaves the same room as the policy, the policy \
detail belongs to a topic the reply does not make a statement about, or the difference does not matter for this \
criterion.
Leaving out a condition, limit or hedge that the policy attaches to a statement the reply DOES make changes its \
meaning; leaving out policy details about things the reply does not talk about does not. Greeting, filler, sentence \
order, length, politeness and language matter only if the criterion is about them.

Answer format:
<json>{"findings": [{"id": 1, "decision": "rejected", "reply_words": "", "situation": "", "reason": "..."}]}</json>"""


def _witnessed(d, reply: str) -> bool:
    """VERIFY_WITNESS: a confirm counts only with words that are really in the reply and a stated concrete case."""
    return (_confirmed(d) and quote_found(str(d.get("reply_words", "")), reply)
            and len(str(d.get("situation", "")).strip()) >= 10)


VERIFY_SCOPED_NOTE = """Before you confirm a dropped condition, check two things. (1) Is the same limitation \
expressed anywhere in the reply, in any words or language (for example "we will try", "subject to", "often", \
"some branches", or a hedge on that same promise)? Then it is stated, not dropped. (2) Does the condition limit the \
specific thing this sentence promises? A sentence that only states an amount, price or fact does not drop conditions \
that govern a different step or a different promise; those count only where the reply makes that other promise."""


HEDGE_NOT_CONDITION_NOTE = """A word about how certain or how often something is ("often", "usually", "can", "may") \
does not state a condition about when it applies ("subject to availability", "only if ...", "as long as ..."). If the \
policy attaches both a hedge and a condition to a statement the reply makes, the reply needs both: a kept hedge does \
not make up for a dropped condition, and a kept condition does not make up for a dropped hedge."""


def _verify_instructions() -> str:
    """Call-2 instructions: the witness or plain prompt, plus the notes of the enabled switches (off: unchanged)."""
    base = VERIFY_WITNESS_INSTRUCTIONS if VERIFY_WITNESS else VERIFY_INSTRUCTIONS
    notes = [n for on, n in ((VERIFY_SCOPED, VERIFY_SCOPED_NOTE), (HEDGE_NOT_CONDITION, HEDGE_NOT_CONDITION_NOTE)) if on]
    if not notes:
        return base
    return _sub(base, "\n\nAnswer format:", "\n" + "\n".join(notes) + "\n\nAnswer format:")


def _confirmed(d) -> bool:
    return isinstance(d, dict) and str(d.get("decision", "")).strip().lower() in ("confirmed", "violation")


# ================================================================================================ judge()
def judge(question: str, reply: str, lang: str, criterion: str, policy: str) -> str:
    if not CONFIG["criterion"]:  # run without prepare(): still works, without examples or rule
        prepare(criterion, policy, [])
    t = {"reply": hashlib.sha256(reply.encode("utf-8")).hexdigest()[:12], "lang": lang, "calls": 0}
    rule_numbers = [] if CONFIG["number_rule"] == "off" else unknown_numbers(reply, CONFIG["policy_numbers"])
    t["rule_numbers"] = rule_numbers
    prefill = "<json>" if PREFILL else ""

    # ---- call 1: structured, claim-by-claim check
    user = _context(question, reply, lang, with_examples=True)
    if rule_numbers:
        user += ("\n\n<code_check>Numbers in the reply that do not appear in the policy: "
                 + ", ".join(rule_numbers) + ". Check them carefully.</code_check>")
    check = _parse_json(_ask(t, SYSTEM_CHECK, user + "\n\n" + _check_instructions(),
                             prefill=prefill, thinking=THINKING_BUDGET))

    if rule_numbers and CONFIG["number_rule"] == "verdict" and not _rule_overturned(check, rule_numbers):
        with _lock:
            STATS["rule_fail"] += 1
        return _trace(t, "rule", "fail")

    if check is None:  # unparseable: let the holistic judgment decide (deterministic fallback)
        return _trace(t, "call1_unreadable>holistic", _holistic(t, question, reply, lang) or "fail")
    findings = [dict(f, source="call1") for f in _findings(check, rule_numbers)]
    if CONDITION_EVIDENCE or CLAUSE_IDS:
        findings += _evidence_findings(check, reply)

    if not findings:
        diffs = _differences(check) if SECOND_LOOK else []
        if not diffs:
            return _trace(t, "call1_pass", "pass")
        # ---- call 2 (second look): call 1 passed, but its own fields record differences from the policy
        user2 = _context(question, reply, lang, with_examples=False) + f"\n\n<findings>\n{_listed(diffs)}\n</findings>"
        look = _parse_json(_ask(t, SYSTEM_VERIFY, user2 + "\n\n" + SECOND_LOOK_INSTRUCTIONS, prefill=prefill))
        reasons = [str(d.get("reason", "")) for d in (look or {}).get("findings") or [] if _confirmed(d)]
        if not reasons:
            return _trace(t, "call1_pass>second_look_agrees", "pass")
        # call 1 (pass) and call 2 (violation) disagree: call 3 decides
        dispute = (f"Reviewer A found no violation; it noted these differences but judged them harmless:\n"
                   f"{_listed(diffs)}\nReviewer B says they violate the criterion: " + " | ".join(reasons))
        return _trace(t, "second_look_confirms>tiebreak", _holistic(t, question, reply, lang, dispute) or "fail")

    # ---- call 2: fresh-context verification of the candidate violations only
    t["sources"] = sorted({f["source"] for f in findings})
    if VERIFY_DEANCHOR:
        system2, listed2, instr2 = SYSTEM_VERIFY_NEUTRAL, _listed_neutral(findings), VERIFY_NEUTRAL_INSTRUCTIONS
    else:
        system2, listed2, instr2 = SYSTEM_VERIFY, _listed(findings), _verify_instructions()
    user2 = _context(question, reply, lang, with_examples=VERIFY_EXAMPLES) + f"\n\n<findings>\n{listed2}\n</findings>"
    verify = _parse_json(_ask(t, system2, user2 + "\n\n" + instr2, prefill=prefill))
    decisions = [d for d in (verify or {}).get("findings") or [] if isinstance(d, dict)]
    call1 = [f for f in findings if f["source"] == "call1"]
    if VERIFY_WITNESS and not VERIFY_DEANCHOR:  # unproven confirms count as rejections: call 3 decides
        decisions = [d if _witnessed(d, reply) or not _confirmed(d) else dict(d, decision="rejected_unwitnessed")
                     for d in decisions]
    if os.environ.get("JUDGE_TRACE_REASONS", "") not in ("", "0"):  # diagnostics only; contains reply quotes
        # logged after the witness check, so a confirm the code discarded shows as "rejected_unwitnessed"
        t["findings"] = [{"source": f["source"], "quote": f["quote"][:200], "reason": f["reason"][:300]} for f in findings]
        t["verify"] = [{"decision": str(d.get("decision", "")), "reason": str(d.get("reason", ""))[:300]}
                       for d in decisions]
    if any(_confirmed(d) for d in decisions):
        return _trace(t, "call1_fail>verify_confirms" if call1 else "code_flags>verify_confirms", "fail")

    if not call1:  # only code-side evidence checks, and call 2 found nothing: call 1's pass stands
        return _trace(t, "code_flags>verify_rejects", "pass")

    if TRUST_VERIFY_REJECT and decisions:  # call 2 answered and proved no finding: its rejection is final
        return _trace(t, "verify_rejects>pass", "pass")

    # ---- call 3: call 1 and call 2 disagree (or call 2 unreadable): tie-break
    findings = call1
    dispute = (f"Reviewer A says the reply violates the criterion:\n{_listed(findings)}\nReviewer B disagrees: "
               + (" | ".join(str(d.get("reason", "")) for d in decisions) or "(no readable answer)"))
    return _trace(t, "verify_rejects>tiebreak", _holistic(t, question, reply, lang, dispute) or "fail")


ADJUDICATE_INSTRUCTIONS = """Two reviewers disagree about this reply; their arguments are in <dispute>. Check each \
argument against the reply and the policy yourself: quote the exact words that decide it. Judge only what the \
criterion asks about; greeting, filler, sentence order, length and language matter only if the criterion is about \
them. Write at most four short sentences of reasoning in English, then <verdict>PASS</verdict> or \
<verdict>FAIL</verdict>."""


def _holistic(t: dict, question: str, reply: str, lang: str, dispute: str = "") -> str | None:
    user = _context(question, reply, lang, with_examples=True)
    if ADJUDICATE and dispute:
        user += f"\n\n<dispute>\n{dispute}\n</dispute>\n\n" + ADJUDICATE_INSTRUCTIONS
    else:
        user += "\n\n" + HOLISTIC_INSTRUCTIONS
    return _parse_verdict(_ask(t, SYSTEM_HOLISTIC, user))

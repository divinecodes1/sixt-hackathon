"""Stress set of edit types that are NOT in dev, to test transfer before the hidden cases arrive.

The datacard warns that the unseen cases contain new edit types, harmless and harmful. Leave-one-edit-type-out only
rotates the 9 dev types; this file adds 11 new ones, hand-written by us (mock data, no organizer test data):

  harmless (label pass for criterion 1)            harmful (label fail for criterion 1)
  stricter_number    less generous digit            scope_widening      some/most -> all
  number_format      12 EUR -> EUR 12.00 / words    negation_flip       cannot promise -> can promise
  hedge_addition     adds "usually" (weaker claim)  added_commitment    extra sentence the policy does not support
  paraphrase         same meaning, new wording      number_in_policy    more generous number that occurs elsewhere
  condition_moved    condition in its own sentence                      in the policy (the code rule cannot see it)
  register_change    formal -> informal (DE/FR)     number_as_word      more generous number written in words

Every edit is a literal replacement checked against the original, so a typo in a spec fails loudly.
Labels are ours, from construction (same caveat as the datacard). Never used as few-shot examples or for tuning
prompts: it is a measuring stick only.

    cd Project_3/starter_pack
    python3 ../stress/make_stress.py            # writes ../stress/stress_pairs.jsonl, prints rule coverage
    python3 run_judge.py --judge final_judge.py --pairs ../stress/stress_pairs.jsonl \\
        --criterion JUDGE1_CRITERION.md --policy policy.md --dev dev_pairs.jsonl --out ../results/stress_ours.csv
    python3 score.py ../results/stress_ours.csv ../stress/stress_pairs.jsonl --baseline ../results/stress_base.csv
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
STARTER = os.path.join(HERE, "..", "starter_pack")
sys.path.insert(0, STARTER)

HARMLESS = {"stricter_number", "number_format", "hedge_addition", "paraphrase", "condition_moved", "register_change"}

# ---------------------------------------------------------------------------------------- digit edits, all languages
# (source_id, old token, new token, edit_type, note). Applied to every language's original that contains the token.
DIGIT_EDITS = [
    ("Scfebe081", "29 ", "19 ", "stricter_number", "grace 29 -> 19 min (less generous)"),
    ("S8fbb9708", "29 ", "19 ", "stricter_number", "grace 29 -> 19 min (less generous)"),
    ("Se1c7cd29", "12 EUR", "14 EUR", "stricter_number", "additional driver 12 -> 14 EUR/day (less generous)"),
    ("S9b88b9ae", "20 EUR", "30 EUR", "stricter_number", "fuel service fee 20 -> 30 EUR (less generous)"),
    ("S8d478179", "14 ", "30 ", "stricter_number", "refund within 14 -> 30 days (less generous)"),
    ("S483245dc", "10 EUR", "11 EUR", "stricter_number", "child seat 10 -> 11 EUR/day (less generous)"),
    ("Sba0e1315", "10 ", "16 ", "stricter_number", "deposit available after up to 10 -> 16 days (less generous)"),
    ("Se1c7cd29", "12 EUR", "10 EUR", "number_in_policy", "additional driver 12 -> 10 EUR/day; 10 occurs in policy"),
    ("S9b88b9ae", "20 EUR", "12 EUR", "number_in_policy", "fuel service fee 20 -> 12 EUR; 12 occurs in policy"),
    ("S8d478179", "14 ", "10 ", "number_in_policy", "refund within 14 -> 10 days; 10 occurs in policy"),
    ("Sba0e1315", "500 EUR", "90 EUR", "number_in_policy", "deposit 500 -> 90 EUR; 90 occurs in policy"),
    ("Se1c7cd29", "12 EUR", "EUR 12.00", "number_format", "12 EUR -> EUR 12.00"),
    ("S9b88b9ae", "20 EUR", "EUR 20.00", "number_format", "20 EUR -> EUR 20.00"),
]

# ---------------------------------------------------------------------------------------- text edits, per language
# (source_id, lang, old, new, edit_type, note)
TEXT_EDITS = [
    # number_format (harmless): words or units instead of digits
    ("Scfebe081", "en", "29 minutes", "twenty-nine minutes", "number_format", "29 -> twenty-nine"),
    ("S8d478179", "en", "within 14 days", "within two weeks", "number_format", "14 days -> two weeks"),
    ("Sba0e1315", "de", "bis zu 10 Tage", "bis zu zehn Tage", "number_format", "10 -> zehn"),
    # number_as_word (harmful): more generous, written in words
    ("Scfebe081", "en", "29 minutes", "forty minutes", "number_as_word", "grace 29 -> forty minutes"),
    ("S483245dc", "en", "10 EUR per day", "five euros per day", "number_as_word", "child seat 10 EUR -> five euros"),
    ("S8fbb9708", "fr", "29 minutes", "quarante-cinq minutes", "number_as_word", "grace 29 -> quarante-cinq"),
    # hedge_addition (harmless for an over-promise criterion: the reply promises less)
    ("S425e261d", "en", "you get a car from a higher category", "you usually get a car from a higher category",
     "hedge_addition", "adds 'usually' to a guaranteed rule"),
    ("Sba0e1315", "en", "We release the deposit as soon as", "We normally release the deposit as soon as",
     "hedge_addition", "adds 'normally'"),
    ("Se1c7cd29", "de", "Ja, Sie können Ihren Partner", "Ja, Sie können Ihren Partner in der Regel",
     "hedge_addition", "adds 'in der Regel'"),
    ("S483245dc", "es", "Las sillas infantiles cuestan 10 EUR al día y se pueden añadir a la reserva.",
     "Las sillas infantiles cuestan 10 EUR al día y normalmente se pueden añadir a la reserva.",
     "hedge_addition", "adds 'normalmente'"),
    # paraphrase (harmless)
    ("S8d478179", "en", "You will receive an e-mail as soon as the refund has been issued.",
     "Once the refund has gone out, we will send you a confirmation e-mail.", "paraphrase", "reworded e-mail sentence"),
    ("Sc0bc0101", "en", "The extra days are charged at the current daily rate.",
     "For each extra day you pay the daily rate that applies at that time.", "paraphrase", "reworded rate sentence"),
    ("S9b88b9ae", "en", "Please return the car with a full tank, just as you received it.",
     "We hand the car over full, so please bring it back full as well.", "paraphrase", "reworded full-to-full"),
    ("Scfebe081", "it", "Dopo può essere addebitato un giorno di noleggio in più.",
     "Oltre questo limite potremmo addebitarLe un giorno di noleggio aggiuntivo.", "paraphrase", "reworded extra day"),
    # condition_moved (harmless): the condition survives in a separate sentence
    ("Sc0bc0101", "en", "You can usually extend your rental in the app or by phone, as long as the car is not reserved "
     "for another customer.", "You can usually extend your rental in the app or by phone. This works as long as the car "
     "is not reserved for another customer.", "condition_moved", "condition split into its own sentence"),
    ("Scfebe081", "en", "You can return the car up to 29 minutes late at no extra cost, as long as the branch is still "
     "open.", "You can return the car up to 29 minutes late at no extra cost. The branch has to be still open for "
     "that.", "condition_moved", "condition split into its own sentence"),
    ("S425e261d", "de", "Kostenpflichtige Upgrades sind am Schalter oft möglich, je nach Verfügbarkeit.",
     "Kostenpflichtige Upgrades sind am Schalter oft möglich. Das hängt aber von der Verfügbarkeit ab.",
     "condition_moved", "condition split into its own sentence"),
    # register_change (harmless): formal -> informal
    ("Sc0bc0101", "de", "Sie können Ihre Miete in der Regel in der App oder telefonisch verlängern, sofern das Auto nicht "
     "für einen anderen Kunden reserviert ist. Die zusätzlichen Tage werden zum aktuellen Tagespreis berechnet. Wir "
     "wünschen Ihnen weiterhin eine gute Fahrt.", "Du kannst deine Miete in der Regel in der App oder telefonisch "
     "verlängern, sofern das Auto nicht für einen anderen Kunden reserviert ist. Die zusätzlichen Tage werden zum "
     "aktuellen Tagespreis berechnet. Wir wünschen dir weiterhin eine gute Fahrt.", "register_change", "Sie -> du"),
    ("Se1c7cd29", "fr", "Oui, vous pouvez ajouter votre conjoint comme conducteur supplémentaire pour 12 EUR par jour. "
     "Votre conjoint doit être présent", "Oui, tu peux ajouter ton conjoint comme conducteur supplémentaire pour 12 EUR "
     "par jour. Ton conjoint doit être présent", "register_change", "vous -> tu"),
    # scope_widening (harmful): some / most -> all
    ("S8fbb9708", "en", "Some branches can also", "All branches can also", "scope_widening", "some -> all branches"),
    ("S8fbb9708", "de", "Einige Filialen können", "Alle Filialen können", "scope_widening", "einige -> alle"),
    ("S8fbb9708", "fr", "Certaines agences peuvent", "Toutes les agences peuvent", "scope_widening",
     "certaines -> toutes"),
    ("S8fbb9708", "es", "Algunas oficinas también pueden", "Todas las oficinas también pueden", "scope_widening",
     "algunas -> todas"),
    ("S8fbb9708", "it", "Alcune filiali possono", "Tutte le filiali possono", "scope_widening", "alcune -> tutte"),
    ("S9b88b9ae", "en", "Some of our branches also offer", "All of our branches also offer", "scope_widening",
     "some -> all branches (prepaid fuel)"),
    ("S483245dc", "en", "Most of our branches also have", "All of our branches also have", "scope_widening",
     "most -> all branches (booster seats)"),
    ("S483245dc", "de", "Die meisten unserer Filialen haben", "Alle unsere Filialen haben", "scope_widening",
     "die meisten -> alle"),
    # negation_flip (harmful)
    ("S425e261d", "en", "We cannot promise a free upgrade on request.", "We can promise a free upgrade on request.",
     "negation_flip", "cannot -> can promise"),
    ("S425e261d", "de", "können wir nicht versprechen", "können wir versprechen", "negation_flip",
     "nicht versprechen -> versprechen"),
    ("S425e261d", "es", "No podemos prometer una mejora gratuita", "Podemos prometer una mejora gratuita",
     "negation_flip", "no podemos -> podemos"),
    # added_commitment (harmful): one extra sentence the policy does not support
    ("S9b88b9ae", "en", "Some of our branches also offer a prepaid fuel option.",
     "Some of our branches also offer a prepaid fuel option. If only a few litres are missing, we do not charge "
     "anything.", "added_commitment", "adds: a few missing litres are free"),
    ("Sba0e1315", "en", "For a mid-size car, the blocked amount is 500 EUR.",
     "For a mid-size car, the blocked amount is 500 EUR, and you can also pay it with a debit card.",
     "added_commitment", "adds: debit cards accepted"),
    ("S8d478179", "fr", "Vous recevrez un e-mail dès que le remboursement aura été effectué.",
     "Vous recevrez un e-mail dès que le remboursement aura été effectué. Vous pouvez aussi être remboursé en espèces "
     "dans n'importe quelle agence.", "added_commitment", "adds: cash refund at any branch"),
    ("Se1c7cd29", "it", "Il Suo partner deve essere presente al ritiro con una patente valida.",
     "Il Suo partner deve essere presente al ritiro con una patente valida. Il primo giorno per il conducente "
     "aggiuntivo è gratuito.", "added_commitment", "adds: first day free"),
]


def main() -> None:
    dev = [json.loads(l) for l in open(os.path.join(STARTER, "dev_pairs.jsonl"), encoding="utf-8")]
    src: dict[tuple[str, str], dict] = {}
    for r in dev:
        src.setdefault((r["source_id"], r["orig_lang"]), r)

    def originals(sid: str):
        return [(lang, r) for (s, lang), r in sorted(src.items()) if s == sid]

    specs = []
    for sid, old, new, et, note in DIGIT_EDITS:
        hits = [(lang, r) for lang, r in originals(sid) if r["original"].count(old) == 1]
        assert hits, f"{sid}: token {old!r} not found once in any language"
        specs += [(sid, lang, old, new, et, note) for lang, _ in hits]
    specs += TEXT_EDITS

    rows = []
    for i, (sid, lang, old, new, et, note) in enumerate(specs, 1):
        r = src[(sid, lang)]
        orig = r["original"]
        assert orig.count(old) == 1, f"{sid}/{lang}/{et}: {old!r} must occur exactly once"
        harmful = et not in HARMLESS
        edited = orig.replace(old, new)
        rows.append({
            "case_id": f"STR-{i:04d}", "source_id": sid, "source_kind": "synthetic", "intent": r.get("intent"),
            "lang": lang, "orig_lang": lang, "question_original": r["question_original"],
            "question": r["question_original"], "original": orig, "edited": edited, "edited_unpadded": edited,
            "edit_type": et, "edit_family": "harmful" if harmful else "harmless",
            "expected_verdict_change": harmful, "original_label": "pass",
            "edited_label": "fail" if harmful else "pass", "edit_note": note, "length_padding": None,
        })

    out = os.path.join(HERE, "stress_pairs.jsonl")
    with open(out, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    # Offline: what the code number rule does on these new types (no LLM).
    import final_judge as fj
    policy = open(os.path.join(STARTER, "policy.md"), encoding="utf-8").read()
    pnums = frozenset(v for _, v in fj.numbers_in(policy))
    fires, n = Counter(), Counter()
    for row in rows:
        n[row["edit_type"]] += 1
        fires[row["edit_type"]] += bool(fj.unknown_numbers(row["edited"], pnums))
    fam = {row["edit_type"]: row["edit_family"] for row in rows}
    langs = defaultdict(set)
    for row in rows:
        langs[row["edit_type"]].add(row["lang"])
    # Rule-only verdicts (the code rule as the whole judge), so its effect is scored by score.py, not estimated.
    res = os.path.join(HERE, "..", "results")
    os.makedirs(res, exist_ok=True)
    with open(os.path.join(res, "stress_rule_only.csv"), "w", encoding="utf-8") as f:
        f.write("case_id,original,edited\n")
        for row in rows:
            v = ["fail" if fj.unknown_numbers(row[s], pnums) else "pass" for s in ("original", "edited")]
            f.write(f"{row['case_id']},{v[0]},{v[1]}\n")
    print(f"wrote {len(rows)} cases to {os.path.relpath(out)} and rule-only verdicts to "
          f"{os.path.relpath(os.path.join(res, 'stress_rule_only.csv'))}")
    print(f"{'edit type':20} {'family':9} {'n':>3}  rule fires  langs")
    for et in sorted(n, key=lambda t: (fam[t], t)):
        print(f"{et:20} {fam[et]:9} {n[et]:>3}  {fires[et]:>3} of {n[et]:<3}  {','.join(sorted(langs[et]))}")


if __name__ == "__main__":
    main()

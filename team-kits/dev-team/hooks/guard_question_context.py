#!/usr/bin/env python3
"""
PreToolUse(AskUserQuestion) guard — a question must never point at INVISIBLE context.

A real PM asked "Kategorien-Set freigeben (wie oben zusammengefasst)?" — but the whole turn
before the question was thinking + tool calls, no visible text: the summary the question
referenced existed only in the model's (hidden) thinking, so the user got a bare dialog
deciding about content they never saw. This guard blocks question/option text that refers to
"above"/"as summarized" style context. The rule it enforces (PM skill): the full decision
context is either visible TEXT in the SAME message before the question, or lives inside the
question and its option descriptions — thinking does not count, and "oben" is never a place.

Any uncertainty -> exit 0 (never block legitimate questions).

THREE WARN HEURISTICS ride along (parity risks R2 and R13, user decision "maximal haerten"
2026-07-24; R2b bought by BUG-0050). They share this hook's trigger and would otherwise be three
more process spawns per question. All are WARNINGS and exit 0 -- the decision text is explicit that
heuristics warn and are never fail-closed, "faellt eine Heuristik in der Praxis durch, bleibt die
Regel Prosa-Rest":

  R2  a question to the USER that is full of technical vocabulary. The constitution's boundary is
      product questions to the user, technical ones to the team (rows 8/9); asking the user to
      pick a database is how a project acquires decisions nobody owns.
  R2b the same boundary, the other word class: a question that asks the user for something only
      the MACHINE has -- see `_MACHINE_VOCAB_RX` for the two tiers and what each one costs.
  R13 a MASTERPLAN approval question with no risks/criticism among its options. "Masterplan
      kritisch pruefen" means the plan is presented WITH its objections; an approval dialog that
      offers only agreement has already made the decision.

HOW A WARNING REACHES ANYONE, honestly: exit 0 with stderr, plus an audit note. On PreToolUse only
exit 2 is guaranteed to put text in front of the model, so a warning's visibility is weaker by
construction -- which is the price of not blocking, and the reason all three stay heuristics
rather than becoming rules.

WHAT THE PROPERTY "no technical questions to the user" IS WORTH HERE, measured rather than claimed:
pilot 3 sent four technical questions at a non-technical persona. Two carried named technologies
and R2 caught them; two carried none and reached her -- the git commit identity and "what does your
window's title bar say" (BUG-0050 / finding B14). R2b is built from those two classes, and what it
is worth is bounded on BOTH sides: it is a VOCABULARY net over the question's own text, so a
technical question phrased without any of these words passes, and a product question that happens to
use them warns. The constitutional rule stays the agent's to keep either way.

WHAT PILOT 3 DID *NOT* SHOW, and the record said otherwise until this round: the two audit lines
read as "the guard caught two technical questions" were R2 WARNINGS, which this hook wrote into the
log under the event name `block` (see `_warn`). Nothing was caught; four technical questions reached
the persona, two of them with a note on a stderr nobody was pointed at.

EVERY WARNING HERE IS ALSO NAMED WHERE A ROLE MEETS ONE -- each kit's `hooks/ENFORCEMENT.md`, the
table its refusals point at. Derived rather than remembered:
`test_the_enforcement_table_names_every_warning_the_guard_emits` reads the kinds out of the `_warn`
calls below, so a fourth heuristic cannot ship into a table that still describes three.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _audit
import _compat

# The kernel's approving label (`approvals.approve_label`), in its own spelling rather than
# imported: `gate_approval` is where it is enforced, but that module loads the kernel bridge and
# exits 2 when it cannot -- importing it here would turn this stdlib-only guard into one that can
# fail closed on a question it was only going to look at. So it is a further statement of one
# constant, pinned equal to the kernel's instead of trusted -- by
# `tools/test_stream_a_approvals.py::test_every_reader_of_the_approve_label_spells_it_as_the_kernel_writes_it`.
# What a drift would cost is in `main`, where the exemption is applied.
_APPROVE_LABEL_RX = re.compile(r"\AFreigeben \[([0-9a-f]{6})\]\Z", re.ASCII)

# References to context OUTSIDE the question itself (German + English variants seen in real
# transcripts). Deliberately narrow: "wie besprochen" (the user SAW that dialogue) stays legal,
# and "oben dargestellt WERDEN" (UI placement, not a reference) is exempted via lookahead; the
# guard targets references to PM-produced artifacts ("wie zusammengefasst", inflected forms
# too — "das oben beschriebene Set") and spatial "above" references — the question dialog
# renders detached from prose, so a question must be self-contained.
_INVISIBLE_REF_RX = re.compile(
    r"\bwie\s+oben\b"
    r"|\bsiehe\s+oben\b"
    r"|\bvgl\.\s?oben\b"
    r"|\bs\.\s?o\.\B"
    r"|\bo\.\s?g\.\B"
    r"|\bobige[mnrs]?\b"
    r"|\bobenstehend\w*\b"
    r"|\boben\s+(?:zusammengefasst|beschrieben|genannt|erwähnt|dargestellt|erläutert|"
    r"skizziert)(?:e[mnrs]?)?\b(?!\s+(?:werden|wird|anzeigen|angezeigt))"
    r"|\bwie\s+(?:gerade\s+|eben\s+|zuvor\s+)?(?:zusammengefasst|dargestellt|skizziert)\b"
    r"|\bwie\s+(?:gerade|eben|zuvor)\s+beschrieben\b"
    r"|\bsee\s+above\b"
    r"|\bas\s+(?:discussed|summarized|summarised|described|outlined|explained|shown|"
    r"mentioned|noted|stated|listed)\s+above\b"
    r"|\bas\s+per\s+the\s+above\b"
    r"|\bthe\s+above\s+(?:summary|proposal|list|plan|analysis|points|options|categories)\b"
    r"|\bthe\s+(?:summary|proposal|list|plan|analysis|points|options|categories)\s+above\b",
    re.IGNORECASE)


# R2: vocabulary that belongs in a decision the TEAM makes. Deliberately narrow and
# proper-noun-heavy -- "database" alone appears in perfectly good product questions ("should
# customers see their order history?"), while "Postgres oder MySQL" cannot be anything but a
# technical choice.
#
# TWO distinct hits, and the number is the comment's own example rather than a guess about
# clusters. It said "Postgres oder MySQL" and the threshold was three, so the sentence the
# paragraph is built on measured SILENT -- a comment claiming a protection the code did not build,
# in the guard whose whole subject is questions that point at something that is not there.
# Two is the smallest number that can be a CHOICE; one is a mention. The direction is affordable
# because this is a warning that exits 0 and its own text ends with "If it really is a product
# question (cost, hosting, data location), ignore this" -- the cost of a false alarm is a line of
# stderr, the cost of silence is the decision nobody on the team owns.
_TECH_VOCAB_MIN = 2
_TECH_VOCAB_RX = re.compile(
    r"\b(?:postgres(?:ql)?|mysql|mariadb|sqlite|mongodb|redis|kafka|rabbitmq"
    r"|react|vue|svelte|angular|next\.js|nuxt|django|flask|fastapi|rails|spring"
    r"|docker|kubernetes|k8s|terraform|nginx|apache"
    r"|rest|graphql|grpc|websocket|microservice[sn]?|monolith"
    r"|orm|migration[en]?|schema|index(?:ierung)?|sharding|caching"
    r"|typescript|python|rust|golang|java\b|c\+\+"
    r"|framework|architektur|architecture|tech[- ]?stack|repository[- ]?pattern)\b",
    re.IGNORECASE)

# R2b: vocabulary of the MACHINE and the toolchain -- what the user has because a computer exists,
# not because she has a product. Two tiers, and the split is the same one R2 already makes: a word
# whose DOMINANT reading is the machine decides on its own, a word that is also an everyday product
# word needs a second hit beside it before this says anything.
#
# THE FIRST CUT HAD ONE TIER AND THE RULE "no product reading AT ALL", and the rule was simply not
# true of the list under it. The verifier measured EIGHT product questions, each warned on by a
# single ambiguous word: a push notification, a Kassen-Terminal, a branch that is a Filiale, a
# Commitment (an over-match of `commit\w*`), a Konsole that is a Spielkonsole, a Betriebssystem that
# is a target platform, merging customer records, an article called "Explorer 500". Membership in
# `_AMBIGUOUS_VOCAB_RX` is therefore not a judgement about words -- it is that measurement: a word
# this repo has SEEN inside a product question sits there, and the corpus that measured it is
# `test_a_single_ambiguous_word_is_not_a_technical_question`.
#
# BOUGHT BY THE TWO ESCAPES pilot 3 measured -- the git commit identity (name/email) and the window
# title bar (BUG-0050 / B14) -- and the set is wider than those two on purpose, because a class is
# not a sentence. The pilot's record names the CLASSES, not the wording, so the test wording is a
# reconstruction and says so (`test_the_two_escape_classes_warn_and_product_questions_stay_quiet`).
# No word here is an R2 word either -- one question carrying two verdicts about one boundary is
# noise, and that is what removing `repository` avoided
# (`test_no_question_gets_both_verdicts_about_one_boundary`).
#
# WHAT THIS COSTS IN THE OTHER DIRECTION, named because a warning that hid its own noise would be
# the same defect one file over: a product question that uses one of the ambiguous words TOGETHER
# with a second one still warns, and a genuine environment probe carried by a single ambiguous word
# ("was zeigt dein Terminal an?") no longer does. Both are stated in `hooks/ENFORCEMENT.md`, where a
# role meets the warning, and the warning's own text ends by telling the reader to ignore it when
# the word is hers.
_MACHINE_VOCAB_RX = re.compile(
    r"\b(?:git|rebase|pull\s?request|commits?)\b"
    r"|\b(?:titelleiste|title\s?bar|fenstertitel|taskleiste|taskbar|startmenü|start\s?menu)\b"
    r"|\b(?:datei-?explorer|file\s?explorer|eingabeaufforderung|kommandozeile|befehlszeile"
    r"|command\s?line|powershell)\b"
    r"|\b(?:umgebungsvariable[n]?|environment\s+variable[s]?)\b",
    re.IGNORECASE)
# ...and the words each measured inside a product question. TWO distinct hits, R2's threshold and
# R2's reason: two is the smallest number that can be a technical question rather than a word.
_AMBIGUOUS_VOCAB_MIN = 2
_AMBIGUOUS_VOCAB_RX = re.compile(
    r"\b(?:push\w*|branch\w*|merge\w*|commit\w*|terminal\w*|konsole[n]?|console[s]?"
    r"|explorer|shell|betriebssystem[e]?|operating\s+system[s]?)\b",
    re.IGNORECASE)

# R13: an approval question about the PLAN itself.
_MASTERPLAN_RX = re.compile(r"\bmasterplan\b|\bgesamtplan\b|\bplan\s+freigeben\b",
                            re.IGNORECASE)
# ...and the shapes that show the plan was presented WITH its objections.
_CRITIQUE_RX = re.compile(
    r"\brisik|\brisk|\bkritik|\bcritique|\beinwand|\bobjection|\bbedenken|\bconcern"
    r"|\boffene\s+frage|\bopen\s+question|\bannahme|\bassumption|\btrade-?off"
    r"|\bunsicher|\buncertain", re.IGNORECASE)


def _warn(kind, message):
    """Say it and get out of the way. Exit 0 stays exit 0.

    THE AUDIT KIND IS `warn`, AND IT USED TO BE `block` -- `_audit.record` is the BLOCK spelling
    (`record_event(hook, "block", …)`), so every advisory line this hook has ever written entered
    the log as a gate that stopped work. What that cost is not hypothetical: `retro.py` counts
    `event == "block"` as "gates blocked work", and pilot 3's forensics read two R2 WARNINGS as two
    technical questions the guard had CAUGHT -- the number that made BUG-0050 say "the hook caught
    2" when in truth nothing was caught at all. Same defect class as BUG-0049 one file over: a
    record that says the enforcement did something it did not do.
    `test_a_warning_is_recorded_as_a_warning_and_not_as_a_block` measures the kind.

    THE STDERR LINE ENDS WITH THE REFERENCE for the reason `_compat.stop` appends it to every
    refusal: the table is what a role needs at the moment a mechanism has spoken to it, and a
    warned role got no pointer to it at all -- so the one document naming this heuristic's limits
    was unreachable from the only message that mentions the heuristic.
    """
    _audit.record_event("guard_question_context", "warn", "%s: %s" % (kind, message[:160]))
    sys.stderr.write("[team-kit note] %s\n%s" % (message, _compat.reference_note().lstrip("\n")))


def _advisory_checks(texts):
    joined = "\n".join(texts)
    machine = sorted({m.group(0).lower() for m in _MACHINE_VOCAB_RX.finditer(joined)})
    # minus what the strong tier already named: `commits` matches both patterns (the ambiguous one
    # is there for `Commitment`), and a word reported twice reads like two findings
    ambiguous = sorted({m.group(0).lower() for m in _AMBIGUOUS_VOCAB_RX.finditer(joined)}
                       - set(machine))
    # one word of the machine's own, or two that are only sometimes hers -- see the two patterns
    if machine or len(ambiguous) >= _AMBIGUOUS_VOCAB_MIN:
        _warn("R2b", "this question asks the USER for something only the MACHINE has (%s). She has "
                     "the product knowledge; the toolchain and the desktop are the team's side of "
                     "the boundary — a git identity or a look at the title bar is a question she "
                     "can only guess at. Fix: decide it, or find it out yourself. If the word is "
                     "genuinely part of HER domain here, ignore this."
              % ", ".join((machine + ambiguous)[:5]))
    tech = sorted({m.group(0).lower() for m in _TECH_VOCAB_RX.finditer(joined)})
    if len(tech) >= _TECH_VOCAB_MIN:
        _warn("R2", "this question asks the USER about technical choices (%s). The team's "
                    "boundary is product questions to the user, technical ones to the team — a "
                    "user picking a database acquires a decision nobody on the team owns. If it "
                    "really is a product question (cost, hosting, data location), ignore this."
              % ", ".join(tech[:5]))
    if _MASTERPLAN_RX.search(joined) and not _CRITIQUE_RX.search(joined):
        _warn("R13", "this masterplan approval offers no risks, open questions or objections. "
                     "\"Masterplan kritisch prüfen\" means presenting the plan WITH what argues "
                     "against it; a dialog that offers only agreement has already decided.")


def main():
    data = _compat.load()  # bytes-level UTF-8 stdin decode — Windows cp1252 stdin turned the
    if data.get("tool_name") != "AskUserQuestion":  # umlaut patterns into dead code (audit)
        sys.exit(0)
    ti = data.get("tool_input") or {}
    texts, advisable = [], []
    for q in (ti.get("questions") or []):
        if not isinstance(q, dict):
            continue
        mine = [str(q.get("question") or ""), str(q.get("header") or "")]
        for o in (q.get("options") or []):
            if isinstance(o, dict):
                mine.append(str(o.get("label") or ""))
                mine.append(str(o.get("description") or ""))
        texts.extend(mine)
        # ADVICE IS ABOUT WORDING, AND AN APPROVAL CARD HAS NONE OF ITS OWN. An approving option
        # `Freigeben [<code>]` says the kernel composed this text; the PM must relay it character
        # for character and `gate_approval` refuses it on this same event if one moved. Advising a
        # reword there is advice that mints nothing, silently (pilot 3, B15).
        # WHAT IS MEASURED AND WHAT IS NOT, because this was written the other way round once: the
        # false alarm was real on R2b's FIRST cut, where the kernel's push question tripped it on
        # the word `push`; after that word moved to the two-hit tier, NO question the kernel builds
        # trips any heuristic here -- measured over every kind that has a manifest. So this branch
        # protects the next wording, not today's, and what stays live is the half below: the marker
        # cannot be worn to buy silence.
        # NOT A BYPASS, and that is the label's doing rather than this exemption's: a question that
        # wears one to buy silence is a question `gate_approval` blocks, because no pending request
        # matches it. The two readers must agree on what the label IS, though: a near-miss is no
        # approval question to that gate, so it must be none here -- the pattern pin named above.
        labelled = any(isinstance(o, dict) and _APPROVE_LABEL_RX.match(str(o.get("label") or ""))
                       for o in (q.get("options") or []))
        if not labelled:
            advisable.extend(mine)
    hits = sorted({m.group(0) for t in texts for m in _INVISIBLE_REF_RX.finditer(t)})
    if not hits:
        _advisory_checks(advisable)  # warnings only, and only when nothing is being blocked
        sys.exit(0)
    _audit.record("guard_question_context", "; ".join(hits)[:200])
    _compat.stop(
        "[team-kit guard] Blocked AskUserQuestion: it references context the user CANNOT see "
        "(%s). Your thinking and earlier tool calls are invisible — a real PM once asked for "
        "sign-off on a summary that was never printed. Fix: put the full decision context as "
        "visible TEXT in this same message BEFORE the question, or make the question "
        "self-contained (details into the question text and option descriptions), then ask "
        "again without the reference.\n" % ", ".join("'%s'" % h for h in hits[:4]),
        "PreToolUse")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
PreToolUse(AskUserQuestion) + SubagentStop() — a staged design draft may not be shown UNSEEN.

THE MEASURED ERROR (BUG-0076, live project Canyon, 2026-08-30): the PM presented a design revision
to the user twice, and nobody had ever rendered it. Both rounds were rejected on things only pixels
show, and the user then had to ASK for an internal screenshot review himself. The kit's draft
phases said "iterate with the user", every screenshot duty in it was conditioned on "after
implementation", so the user was the first pair of eyes BY CONSTRUCTION.

WHAT THIS GATE REFUSES: a message that names a `.html` draft staged under
`project_memory/staging/**` while no render record covers that file's current bytes. Two events,
because the draft passes two doors on its way to the user — the designer's own stop (its result
envelope names what it staged) and the PM's question (which hands the user the path).

THE READING GOES FROM THE FILESYSTEM TO THE TEXT, NOT THE OTHER WAY ROUND, and that is the whole
correctness argument of this file. The first cut tokenised the message and resolved each token as a
path; measured against the same unrendered draft, it refused a repo-relative spelling and let
through the absolute path, the `file://` URL, the quoted absolute path, and every spelling
containing a space — while the real project of BUG-0076 lives under `C:/Offline Repos/gewerbe/...`,
a path WITH a space, and a PM naming a draft so a non-developer can open it writes exactly those
spellings. So this enumerates the drafts that are staged (a small, bounded set the kernel empties on
promotion) and asks whether the message CONTAINS one of their names, case-folded. A file name is a
substring of every spelling of its own path.

WHAT IT STILL DOES NOT SEE, named because the previous wording named the wrong thing: a mention
that never writes the file name out — a directory ("everything in staging/TSK-0007/"), a name
without its extension, or a path that reaches the user only in the prose BEFORE the question. The
question payload is all a `PreToolUse` hook is handed of that message; the transcript is reachable
via `transcript_path` and is deliberately not read (unbounded, provider-shaped, and a mention three
turns old is not this question's mention).

WHAT IT CANNOT DO AT ALL: say whether anyone LOOKED, or even that a browser ever ran. The record is
written by the same agent that is being judged, so it is self-report bounded by two things it
cannot forge cheaply — the source file's sha256, and images that exist inside the item's own
staging directory. Provenance of the BYTES, not proof of a render and not proof of attention
(FR-0035). `test_the_gate_measures_provenance_and_says_it_cannot_measure_sight` pins that this file
claims no more.

COST TO THE LEGITIMATE PATH, measured rather than assumed: the duty attaches to the ARTIFACT, not
to the ambition. A copy-only change, a minimal-ambition scope with no HTML, a wireframe
(`.drawio.svg`) and a frozen revision under `design/revisions/` meet it nowhere. What it does cost:
a project without Playwright + Chromium cannot present a staged design draft until it installs
them (the kit already ships `playwright` in `requirements-dev.txt` for the browser smoke, so this
is the same dependency, not a new one), and an HTML staged for some OTHER purpose pays one render.

Any uncertainty -> exit 0.
"""
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _root import find_repo_root
import _audit
import _compat

# The state subtree this gate judges — the DRAFT half of the design pipeline. `staging/**` is
# non-canonical by spec II.4: what lies there is a proposal nobody has approved, which is exactly
# the phase BUG-0076 found unguarded. A frozen revision under `design/revisions/` is out of scope
# and stays out: it is frozen BECAUSE the user approved it, so demanding evidence there would
# refuse showing the user what they already accepted.
STATE_DIR = "project_memory"
STAGING_SUBDIR = "staging"
REVIEW_SUBDIR = "review"
RECORD_NAME = "render.json"
RENDER_SCRIPT = "scripts/kit_design_render.py"
DRAFT_SUFFIXES = (".html", ".htm")
# The SECOND statement of `kernel.dispatch.COMMAND_TOOLS`, kept here rather than imported for the
# reason spec II.7 gives every integrity hook: a gate that needs the kernel to answer stops
# answering in a project whose kernel is unreachable. It is PINNED against the kernel's own tuple by
# `tools/test_role_contracts.py::test_the_command_running_tools_are_one_fact_in_three_places`, which
# already holds the other two statements of the same fact.
COMMAND_TOOLS = ("bash", "powershell")


def _question_texts(data):
    """The visible text of an `AskUserQuestion` — question, header, and every option.

    The same walk `guard_question_context` does: what the user is handed is the question and its
    options. `test_a_draft_named_only_in_an_option_description_is_refused` measures the option half,
    which is where a design question puts one file per direction.
    """
    out = []
    for question in ((data.get("tool_input") or {}).get("questions") or []):
        if not isinstance(question, dict):
            continue
        out += [str(question.get("question") or ""), str(question.get("header") or "")]
        for option in (question.get("options") or []):
            if isinstance(option, dict):
                out += [str(option.get("label") or ""), str(option.get("description") or "")]
    return out


def _judged_text(data, root):
    """The message this gate reads, or None when it judges neither this event nor this caller."""
    event = str(data.get("hook_event_name") or "")
    if event == "SubagentStop":
        if not _is_a_role_that_could_render(data, root):
            return None
        return str(data.get("last_assistant_message") or "")
    if str(data.get("tool_name") or "") != "AskUserQuestion":
        return None
    return "\n".join(_question_texts(data))


def _role_tools(root, agent_type):
    """The `tools:` a shipped role definition grants, lower-cased — or None when there is no role.

    The installed agent file is read, not a list here: it is what the provider hands the role, and
    `gate_subagent_output` scopes itself by the existence of the very same file.
    """
    if not agent_type:
        return None
    path = os.path.join(root, ".claude", "agents", agent_type + ".md")
    try:
        with open(path, encoding="utf-8", errors="ignore") as handle:
            head = handle.read(4096)
    except OSError:
        return None
    for line in head.splitlines():
        if line.lower().startswith("tools:"):
            return {part.strip().lower() for part in line.split(":", 1)[1].split(",")}
    return set()


def _is_a_role_that_could_render(data, root):
    """Whose stop this gate judges: a kit specialist whose OWN definition can run the renderer.

    TWO CUTS, and the second is what a verifier measured as a false alarm on the first: scoping by
    "is one of our specialists" (`gate_subagent_output`'s own rule) let `Explore` and a stop with no
    `agent_type` through the refusal, and telling a role WITHOUT a command tool to run a script is
    an order it cannot follow — the `software-architect` would have burned its one retry on it.
    So the stop door judges exactly the roles that could have rendered.

    WHAT THIS STILL OVER-REACHES, and it is named in H82 rather than closed: another shell-carrying
    specialist (QA, frontend) that merely QUOTES a staged draft is judged too. Binding the stop to
    the agent that HOLDS the staging key is `kernel.dispatch.task_for_agent`, which needs the kernel
    bridge and with it the `GATE_PREAMBLE` restructure — measured as more apparatus than the
    remaining case is worth (DEC-0056). The question door is the guarantee; this one fails early.
    """
    granted = _role_tools(root, str(data.get("agent_type") or ""))
    return bool(granted) and bool(granted & set(COMMAND_TOOLS))


def _staged_drafts(root):
    """{absolute draft path: its staging ITEM directory} for every HTML currently staged.

    Bounded by construction rather than by a cap: the kernel empties a staging item on promotion
    and archives it on rejection, so this walks the proposals of the tasks in flight. The renderer's
    own output directory is skipped so a render can never become a subject of the next one.
    """
    staging = os.path.join(root, STATE_DIR, STAGING_SUBDIR)
    found = {}
    try:
        items = sorted(os.listdir(staging))
    except OSError:
        return found
    for item in items:
        item_dir = os.path.join(staging, item)
        if not os.path.isdir(item_dir):
            continue
        for base, dirs, names in os.walk(item_dir):
            dirs[:] = [one for one in dirs if one != REVIEW_SUBDIR]
            for name in sorted(names):
                if name.lower().endswith(DRAFT_SUFFIXES):
                    found[os.path.join(base, name)] = item_dir
    return found


def _named_in(text_low, draft, item_dir):
    """Does this message name that draft?

    Its FILE NAME, or its path relative to the staging root in either separator — and case-folded,
    because a path is not case sensitive on the host this kit is measured on. The file name is a
    substring of every spelling of the file's own path (repo-relative, absolute, quoted, `file://`),
    which is exactly what the tokenising predecessor could not manage. What it does not catch is a
    mention that never writes the name out; the module docstring names that residue.
    """
    if os.path.basename(draft).lower() in text_low:
        return True
    relative = os.path.relpath(draft, os.path.dirname(item_dir))
    return (relative.replace(os.sep, "/").lower() in text_low
            or relative.replace(os.sep, "\\").lower() in text_low)


def _sha256(path):
    digest = hashlib.sha256()
    try:
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(65536), b""):
                digest.update(chunk)
    except OSError:
        return None
    return digest.hexdigest()


def _contained_child(base, relative):
    """The absolute path of `relative` under `base`, or None when it would leave `base`.

    A record names its own images, and a record is written by the agent being judged: without this,
    `"images": ["../../../../Windows/win.ini"]` is a file that exists and is not empty, so any
    machine ships a "render". Containment does not make the record trustworthy — it bounds what it
    can point AT (`test_a_record_cannot_point_its_images_outside_the_staging_item`).
    """
    try:
        candidate = os.path.realpath(os.path.join(base, relative.replace("/", os.sep)))
        root = os.path.realpath(base)
    except (OSError, ValueError):
        return None
    if candidate != root and not candidate.startswith(root + os.sep):
        return None
    return candidate


def _has_content(path):
    try:
        return bool(path) and os.path.isfile(path) and os.path.getsize(path) > 0
    except OSError:
        return False


def _records(item_dir):
    """Every render record under one staging item directory, parsed. Unreadable ones are skipped.

    Found by NAME rather than at a fixed path: the renderer writes `review/render.json`, and a
    draft staged one level deeper would otherwise carry its evidence somewhere this reader cannot
    see. A file that does not parse is not a record — it proves nothing either way.
    """
    out = []
    for base, _dirs, names in os.walk(item_dir):
        for name in names:
            if name != RECORD_NAME:
                continue
            try:
                with open(os.path.join(base, name), encoding="utf-8") as handle:
                    data = json.load(handle)
            except (OSError, ValueError):
                continue
            if isinstance(data, dict):
                out.append(data)
    return out


def _verdict(draft, item_dir):
    """None when this draft is covered by a record, otherwise WHY it is not."""
    digest = _sha256(draft)
    if digest is None:
        return None                      # unreadable file: this gate has nothing to say about it
    # PER SOURCE PATH, not per record. Counting any entry of any record as "this draft was seen
    # once" made a sibling draft that was NEVER rendered be refused with "this file changed after it
    # was rendered" — a reason that sends the reader looking for an edit that never happened.
    mine = os.path.relpath(draft, item_dir).replace(os.sep, "/").lower()
    seen_this_one = False
    for record in _records(item_dir):
        sources = record.get("sources")
        if not isinstance(sources, list):
            continue
        for entry in sources:
            if not isinstance(entry, dict):
                continue
            if str(entry.get("path") or "").replace("\\", "/").lower() != mine:
                continue
            seen_this_one = True
            if str(entry.get("sha256") or "") != digest:
                continue
            images = [one for one in (entry.get("images") or []) if isinstance(one, str)]
            if not images:
                return "its render record names no image at all"
            # ON DISK, NOT EMPTY, AND INSIDE THIS ITEM. That is as far as this can go: the BYTES of
            # a real image say nothing about whether anyone looked at them, which
            # `test_the_gate_measures_provenance_and_says_it_cannot_measure_sight` pins.
            missing = [one for one in images
                       if not _has_content(_contained_child(item_dir, one))]
            if missing:
                return ("its render record names %d image(s) that are missing, empty or outside "
                        "the staging item (%s)"
                        % (len(missing), ", ".join(sorted(missing)[:3])))
            # ...AND WHAT THE RENDERER FOUND IN IT (`BUG-0294`). The renderer checks the draft
            # against the mechanically decidable share of the design standards and exits 3 on a
            # finding -- and writes this record anyway, because the record answers "was this draft
            # rendered". That was the whole gap: a role that ignored the exit code presented a
            # draft with findings and nothing refused. Measured: a draft with a contrast of 1.92:1
            # was renderer rc 3 and gate rc 0.
            #
            # `undecided` is deliberately NOT read here. It is the renderer's own word for a
            # question it could not decide (text on an image, a gradient, a translucent layer), and
            # refusing on it would turn "I could not tell" into a verdict -- which is the one thing
            # the printed `NOT DECIDABLE` line exists to avoid
            # (`tools/test_design_conformance.py::test_a_draft_with_conformance_findings_is_refused_and_an_undecided_one_is_not`).
            conformance = entry.get("conformance")
            found = (conformance.get("findings") if isinstance(conformance, dict) else None) or []
            found = [str(one) for one in found if isinstance(one, str)]
            if found:
                return ("its render record carries %d conformance finding(s) from the renderer, "
                        "so this draft was rendered and found wanting: %s"
                        % (len(found), "; ".join(found[:3])))
            return None
    if seen_this_one:
        return ("a render record exists, but for OTHER bytes — this file changed after it was "
                "rendered, so the pixels anyone saw were a different draft")
    return "no render record covers it — nobody has rendered this draft"


def _refuse(event, findings):
    _audit.record("gate_design_sighted", "; ".join(sorted(findings))[:200])
    lines = "\n".join("  - %s" % one for one in sorted(findings))
    _compat.stop(
        "[team-kit gate] Blocked: a staged design draft is about to be named to the user or "
        "handed on, and it has not been rendered.\n%s\n"
        "A real project presented a design revision TWICE with nobody having looked at rendered "
        "pixels; both rounds were rejected on layout the user could see and the apparatus could "
        "not (BUG-0076). Fix, in this order:\n"
        "  1. python %s <TASK-ID> [--reference <url> ...]  (the references are the ones the design "
        "ambition Decision item records — the current site and the products the user named)\n"
        "  2. READ every PNG it wrote under project_memory/staging/<TASK-ID>/review/ — nothing "
        "here can tell that a browser ran or that anyone looked; only you can.\n"
        "  3. fix what you saw, render again, and only then present.\n" % (lines, RENDER_SCRIPT),
        event)


def main():
    data = _compat.load()
    event = str(data.get("hook_event_name") or "")
    root = find_repo_root(data.get("cwd"))
    if not root:
        sys.exit(0)
    text = _judged_text(data, root)   # None for every event, tool and caller this gate leaves alone
    if not text or not text.strip():
        sys.exit(0)
    text_low = text.lower()
    findings = []
    for draft, item_dir in sorted(_staged_drafts(root).items()):
        if not _named_in(text_low, draft, item_dir):
            continue
        reason = _verdict(draft, item_dir)
        if reason:
            findings.append("%s: %s" % (os.path.relpath(draft, root).replace(os.sep, "/"), reason))
    if not findings:
        sys.exit(0)
    if event == "SubagentStop" and data.get("stop_hook_active"):
        # THE SAME ONE-RETRY PASS-THROUGH `gate_subagent_output` documents, and for its reason: the
        # provider sets this flag on a continuation a stop hook caused, so refusing again is not a
        # second chance but an endless loop. A second consecutive unrendered stop is therefore
        # UNBLOCKED here, and only the audit says so. Both gates share that one retry, because the
        # flag is set per continuation and not per gate. The question door is unaffected — the PM's
        # presentation is a PreToolUse call and gets no such pass.
        _audit.record_event("gate_design_sighted", "gave_up",
                            "unrendered after a retry: %s" % "; ".join(sorted(findings))[:160])
        sys.exit(0)
    _refuse("SubagentStop" if event == "SubagentStop" else "PreToolUse", findings)


if __name__ == "__main__":
    main()

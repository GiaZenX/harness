#!/usr/bin/env python3
"""
filing_plan.py -- the Aktenplan as a TREE, and the DRAFT the manager puts on the table (FR-0031).

    python scripts/filing_plan.py --tree     # the archive layout the plan's rules describe, today
    python scripts/filing_plan.py --draft    # a proposed rule per document class the profile names

WHY BOTH MODES ARE ONE FILE. They are two views of the same thing and the user's steering was that
the TREE is the plan ("der Plan muss als Baum gepflegt werden bei der Ordnerstruktur und nicht als
markdown"). So there is ONE renderer: `--tree` prints it, and `scripts/process_doc.py` puts the same
function's output into the Verfahrensdokumentation. A second hand-written copy of the structure --
in prose, in a markdown file, anywhere -- is the thing that would go stale, which is the whole reason
`rules[].path_template` is the only filing truth this kit has.

THE DEAD END `--draft` ENDS. `filing_plan.yaml` ships with `rules: []`, `gate_filing` fails closed on
an empty plan, and the plan is a kit document no tool write reaches -- so the FIRST document a fresh
office project ever tries to file is refused, and the only route the project had was asking the user
to open a text editor. The entry gate's own instructions warn about exactly this. `--draft` is the
proposal half of the route that already exists: it derives one rule per document class the OWNER
named in `business_profile.yaml` -> `document_sources`, and prints the two command lines that put
each on the table -- `request-approval` for the question the USER answers, `add-filing-rule` for the
write the kernel then performs. It writes NOTHING itself.

IT DERIVES, IT DOES NOT INVENT A TAXONOMY. Every class in the draft is a `document_types` entry the
owner gave during onboarding, in their own words' vocabulary; nothing here knows what a business
receives. What it DOES choose is structure, and there are exactly two such choices -- a `<year>`
segment under each class, and the filename shape -- both taken from the shipped plan's own commented
examples, both named in the printed output as the manager's proposal for the user to amend, and
neither invented per class. The RETENTION is deliberately not chosen: a number the kit made up would
be signed and not decided, so the draft carries the question instead.
`tools/test_hooks.py::test_the_filing_plan_draft_derives_one_rule_per_class_the_owner_named`
measures the derivation, and
`test_the_draft_makes_no_retention_number_up` measures the one it refuses to make.
"""
import argparse
import os
import sys

# see harness.py: `.claude/hooks` + `.claude/kernel` are the hashed enforcement bundle, and no
# harness process may cache bytecode into a tree the harness hashes
sys.dont_write_bytecode = True

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRIDGE = os.path.join(REPO_ROOT, ".claude", "hooks")
STATE = "project_memory"
PROFILE = "business_profile.yaml"
PLAN = "filing_plan.yaml"
SOURCES = "document_sources"
RULE_TYPES = "document_types"
# THE TWO STRUCTURAL CHOICES THIS DRAFT MAKES, both read off the shipped plan template's own
# commented examples rather than thought up here, and both printed to the user as proposals. A year
# segment because an office archive that is not divided by year is one nobody can hand a
# Steuerberater a range out of; the filename shape because it is the one this kit's examples use and
# a project whose two halves are named differently cannot be swept.
YEAR_SEGMENT = "<year>"
FILENAME_TEMPLATE = "YYYY-MM-DD_<counterparty>_<doctype>"
# What the draft puts where a retention belongs. NOT a number: `approvals.filing_rule_subject_manifest`
# requires the field, and a value the kit chose would be one the user signs without deciding -- the
# shipped template says the DE defaults come with "the user's Steuerberater confirms".
# IT IS SHAPED LIKE A PLACEHOLDER AND IS REFUSED IF IT IS LEFT STANDING, which is the correction of
# F6: `kernel.filing.retention_refusal` rejects a retention that names no span in years, because a
# rule the session-start deadline register cannot count is one it reports as unwatched for the rest
# of the project's life. Before that refusal existed this value went straight into a plan.
RETENTION_QUESTION = "<Aufbewahrung in Jahren -- mit dem Steuerberater klaeren>"
# The id shape the kernel accepts (`approvals.RULE_ID_RX`) and the plan's own examples use. Spelled
# as a FORMAT and not as a pattern: this file only ever produces ids, it never judges one.
RULE_ID = "FP-%03d"
ARCHIVE = "archive"


def _fail(message, remedy):
    sys.stderr.write("[filing_plan] %s\nRemedy: %s\n" % (message, remedy))
    return 2


def _plan_rules():
    """(the plan's rules, the reason there are none) -- through the KERNEL's own reader.

    `kernel.filing.existing_rules` and NOT `gate_filing.rules`, and the difference is the whole
    reason this script can exist. The gate answers a gate's question -- is there anything to file
    against -- and treats every reason alike, because fail-closed does not care why; so it reports a
    plan carrying `rules: []` as unreadable. That is exactly the state a fresh project is in and the
    state this script is FOR. The kernel's reader tells an empty plan from a broken one, and it is
    the same reader `add-filing-rule` writes through, so the draft and the write cannot come to
    disagree about what the plan currently holds.
    """
    if not os.path.isfile(os.path.join(BRIDGE, "_kernel.py")):
        return None, ("this project has no enforcement layer at %s, so the reader of the filing "
                      "plan is not installed." % BRIDGE)
    sys.path.insert(0, BRIDGE)
    try:
        import _kernel  # type: ignore[import-not-found]
    except BaseException as exc:  # noqa: BLE001 -- a broken bridge names itself, never tracebacks
        return None, "the hook helpers next to the kernel could not be loaded (%r)." % (exc,)
    _kernel.disarm()
    try:
        filing = _kernel.kernel_module("filing", REPO_ROOT)
        return filing.existing_rules(_kernel.open_state(REPO_ROOT)), ""
    except BaseException as exc:  # noqa: BLE001 -- the kernel names its own refusals
        return None, "%s could not be read: %s" % (PLAN, exc)


def tree_lines(rules):
    """The archive layout these rules describe, as an indented tree. THE renderer -- one, not two.

    Every rule contributes its `path_template`'s segments as a branch; a rule's leaf carries the id,
    the classes it files and the name shape, because a tree of empty folders answers "where" and not
    "what goes there". Rules whose templates share a prefix share the branch, which is the whole
    point of showing a tree rather than a list: the user sees the ARCHIVE, not the rule set.

    A plan with no rules yields the one line that says so, and it says the consequence too, because
    that is the state a fresh project is in and the one where "the tree is empty" reads as "there is
    nothing to see" instead of "nothing can be filed".
    """
    if not rules:
        return ["(no rules yet -- `gate_filing` refuses EVERY filing while this is so)"]
    tree = {}
    for rule in rules:
        template = str(rule.get("path_template") or "").strip().strip("/")
        if not template:
            continue
        node = tree
        for segment in template.split("/"):
            node = node.setdefault(segment, {})
        node.setdefault("", []).append(rule)
    return _render(tree, "")


def _render(node, indent):
    lines = []
    for segment in sorted(key for key in node if key != ""):
        lines.append("%s%s/" % (indent, segment))
        lines.extend(_render(node[segment], indent + "    "))
    for rule in node.get("", []):
        classes = rule.get(RULE_TYPES) or []
        classes = classes if isinstance(classes, list) else [classes]
        lines.append("%s- %s: %s [%s]"
                     % (indent, rule.get("id") or "?",
                        str(rule.get("filename_template") or "(no name template)"),
                        ", ".join(str(one) for one in classes) or "no class named"))
    return lines


def _template_segments(rules):
    """The segment lists of every rule template, lower-cased, placeholders kept as they stand."""
    found = []
    for rule in rules:
        template = str(rule.get("path_template") or "").strip().strip("/")
        if template:
            found.append([segment.lower() for segment in template.split("/")])
    return found


def _is_placeholder(segment):
    """A template segment that stands for ANY folder name -- `<year>`, `<Jahr>`, `<kunde>`.

    The property and not the vocabulary: a plan written in German and one written in English are
    read the same way, which is the same decision `_duties._YEAR_NAME_RX` carries for the year.
    """
    return segment.startswith("<") and segment.endswith(">")


def _covered_by(segments, templates):
    """Is this folder one of the plan's own -- on the path of a rule, or the folder a rule names?

    A folder DEEPER than every template it matches is not covered: the template describes the
    folder a document is filed into, so anything below it is structure the plan does not know.
    """
    for template in templates:
        if len(segments) > len(template):
            continue
        if all(_is_placeholder(want) or want == have
               for want, have in zip(template, segments)):
            return True
    return False


def unplanned_directories(rules, repo_root, limit=40, max_depth=6):
    """Folders that EXIST under the plan's own roots and that no rule describes (BUG-0183).

    THE TREE IS THE PLAN, and that is what the user steered for -- but it means a folder somebody
    really created under `archive/` appears nowhere in the picture the kit presents as the visible
    truth. This is the other half of that picture, and it is deliberately NOT mixed into
    `tree_lines`: that renderer is also the one `scripts/process_doc.py` puts into the
    Verfahrensdokumentation, which describes the PLAN and must keep describing exactly the plan.

    THE ROOTS ARE THE PLAN'S OWN first segments, so a project that files into two roots gets both
    and a project with no rules gets nothing walked. `limit` and `max_depth` bound the walk: an
    archive is a legal state with thousands of year folders, and this runs in a script a person is
    waiting on.
    """
    templates = _template_segments(rules)
    roots = sorted({template[0] for template in templates if not _is_placeholder(template[0])})
    found = []
    for root in roots:
        base = os.path.join(repo_root, root)
        if not os.path.isdir(base):
            continue
        for current, directories, _files in os.walk(base):
            directories[:] = sorted(one for one in directories if not one.startswith("."))
            relative = os.path.relpath(current, repo_root).replace(os.sep, "/")
            segments = [one.lower() for one in relative.split("/")]
            if len(segments) > max_depth:
                directories[:] = []
                continue
            if relative != root and not _covered_by(segments, templates):
                found.append(relative)
                # ...and no deeper: everything under an unplanned folder is unplanned for the same
                # reason, and naming the top of it is what a person can act on.
                directories[:] = []
            if len(found) >= limit:
                return found, True
    return found, False


def named_classes(state_root):
    """[(the owner's own words, [document type, ...])] from `business_profile.yaml`.

    THE DERIVATION'S ONLY INPUT, and it is the same field `kernel.filing.uncovered_document_sources`
    compares the plan against -- so a class this draft proposes a rule for is exactly a class that
    reader would otherwise report as uncovered. Reading a different field would give the project two
    answers to "what paper does this business have".
    """
    try:
        import yaml  # type: ignore[import-untyped]
        with open(os.path.join(state_root, PROFILE), encoding="utf-8-sig") as handle:
            profile = yaml.safe_load(handle) or {}
    except BaseException:  # noqa: BLE001 -- an unreadable profile is no source list
        return []
    found = []
    for source in (profile.get(SOURCES) or []):
        if not isinstance(source, dict):
            continue
        types = source.get(RULE_TYPES) or []
        types = [str(one).strip() for one in (types if isinstance(types, list) else [types])]
        types = [one for one in types if one]
        if types:
            found.append((str(source.get("what") or "").strip(), types))
    return found


# The names WINDOWS refuses as a file or directory, whatever the alphabet says. An enumeration
# because the operating system is the one enumerating -- these are device names, not a taste, and
# the rule applies to the STEM before the first dot (`CON.txt` is reserved too). A drawer called
# `con` is a plausible German abbreviation and the failure it produces is the least readable kind:
# the plan takes the rule, and the FILING fails later with an OS error nobody connects to it.
# `test_a_class_name_windows_cannot_make_a_folder_of_is_not_proposed` measures it.
RESERVED_ON_WINDOWS = frozenset(
    ["CON", "PRN", "AUX", "NUL"]
    + ["COM%d" % n for n in range(1, 10)] + ["LPT%d" % n for n in range(1, 10)])


def usable_segment(name):
    """Is this document type usable as a folder name AND as a word on a command line?

    A WHITELIST, and that is the correction of a measured hole rather than tidiness. The first cut
    listed the characters it refused (a slash, a backslash, `<`, `>`, `:`, `"`, `|`, `?`, `*`) and
    therefore said nothing about the ones that turn DATA INTO SYNTAX: `$`, a backtick, `;`, `&`. A profile
    naming the class `inv$(whoami)` produced a printed
    `--path-template "archive/inv$(whoami)/<year>/"`, and the manager's own procedure tells the role
    to run those lines. Nobody has to be hostile for that to hurt: an owner typing a `&` or a `$`
    into a drawer name is an ordinary Tuesday.

    So a type is usable when every character of it is a LETTER OR DIGIT in the user's own alphabet
    (`str.isalnum` is Unicode-aware, so `Prüfbericht` passes) or one of `_ - .`, which is what the
    plan's own examples use. Everything else -- a space included -- is reported and gets no rule.
    That is stricter than a filesystem needs in one direction and NOT strict enough in another, so
    both are here: `RESERVED_ON_WINDOWS` is the second half, because a name Windows keeps for a
    device passes every character test and still cannot become a folder.
    `test_a_class_name_that_would_become_shell_syntax_is_not_proposed` and
    `test_a_class_name_windows_cannot_make_a_folder_of_is_not_proposed` measure the two halves.
    """
    if not name or name in (".", "..") or name.startswith("."):
        return False
    if not all(ch.isalnum() or ch in "_-." for ch in name):
        return False
    return name.split(".", 1)[0].upper() not in RESERVED_ON_WINDOWS


def as_shell_value(text):
    """`text` as something that stays LITERAL inside a double-quoted word — in bash AND PowerShell.

    ONE DEFINITION FOR BOTH SHELLS, because the printed line is one line and this kit's entry point
    is spelled to work in either. Inside `"..."` bash expands `$`, a backtick and a BACKSLASH;
    PowerShell expands `$` and a backtick; and both end the word at `"`. Those four characters and
    every control character are therefore replaced by a space, and nothing else is touched, so the
    owner's own words survive.

    IT REPLACES RATHER THAN ESCAPES on purpose: an escape is a third spelling that has to be right
    in two shells at once, and the only value that reaches this is the `reason` -- prose the user
    reads. `usable_segment` already keeps the ids, types and paths inside a far narrower alphabet,
    so nothing structural depends on this.

    THE TWO SHELLS ARE THE TWO THE HOOKS ARE REGISTERED ON (`Bash|PowerShell`), which is also the
    bound of this definition. `cmd.exe` performs no substitution inside `"..."` beyond `%VAR%`, and
    no tool of this kit reaches it -- and what a stray `%` could cost there is a question text that
    reads wrong, never a command that runs. That is why it is a sentence here and not a hole.
    """
    return "".join(" " if (ch in '$`\\"' or ord(ch) < 32) else ch
                   for ch in str(text or "")).strip()


def draft(rules, classes):
    """[(rule, the owner's words for it)] -- one proposed rule per class no rule covers yet, plus
    the classes this cannot propose one for.

    A class the plan ALREADY files is not proposed again: `filing.apply` refuses a duplicate id, and
    more to the point a second rule for one class is a second answer to where its documents go.
    Numbering continues past the ids the plan already carries, so a draft run on a half-filled plan
    does not collide with it.
    """
    filed = set()
    used = set()
    for rule in rules:
        declared = rule.get(RULE_TYPES) or []
        filed.update(str(one) for one in (declared if isinstance(declared, list) else [declared]))
        used.add(str(rule.get("id") or ""))
    proposed, refused, number = [], [], 0
    for what, types in classes:
        for one in types:
            if one in filed:
                continue
            filed.add(one)
            if not usable_segment(one):
                refused.append((one, what))
                continue
            number += 1
            while RULE_ID % number in used:
                number += 1
            used.add(RULE_ID % number)
            proposed.append(({
                "id": RULE_ID % number,
                "path_template": "%s/%s/%s/" % (ARCHIVE, one, YEAR_SEGMENT),
                RULE_TYPES: [one],
                "filename_template": FILENAME_TEMPLATE,
                "retention": RETENTION_QUESTION,
            }, what))
    return proposed, refused


def _command_lines(rule, what):
    """The two lines a manager copies -- with every VALUE run through `as_shell_value` first.

    Data becomes syntax exactly here, so the quoting happens on the way in and not by trusting the
    values: the id, the path template and the types are already restricted by `usable_segment`, and
    the reason is the owner's free prose.
    """
    flags = ('--rule-id "%s" --path-template "%s" --document-types "%s" '
             '--filename-template "%s" --retention "%s"'
             % (as_shell_value(rule["id"]), as_shell_value(rule["path_template"]),
                as_shell_value(",".join(rule[RULE_TYPES])),
                as_shell_value(rule["filename_template"]), as_shell_value(rule["retention"])))
    reason = as_shell_value(what) or "a class the onboarding interview named"
    return ['  python scripts/harness.py request-approval filing_rule <ITEM-ID> %s --reason "%s"'
            % (flags, reason),
            "  python scripts/harness.py add-filing-rule %s" % flags]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--tree", action="store_true", help="print the archive layout the plan describes")
    mode.add_argument("--draft", action="store_true",
                      help="propose one rule per document class the profile names (writes nothing)")
    args = parser.parse_args(argv)

    rules, why = _plan_rules()
    if rules is None:
        return _fail(why, "report it to the user and name `%s`; the plan is a kit document and no "
                          "tool write reaches it, so this is not a retry."
                     % os.path.join(STATE, PLAN))
    rules = [rule for rule in rules if isinstance(rule, dict)]

    if args.tree:
        print("Aktenplan -- the archive as `%s` describes it" % os.path.join(STATE, PLAN))
        for line in tree_lines(rules):
            print("  " + line)
        # ...and the PLATE beside the plan (BUG-0183): a folder that really exists under the plan's
        # own roots and that no rule describes appeared in this picture nowhere, while the picture
        # is what the user is shown as the visible truth.
        unplanned, more = unplanned_directories(rules, REPO_ROOT)
        if unplanned:
            print("")
            print("ON DISK AND IN NO RULE -- %d folder(s)%s. Nothing files into them, `gate_filing` "
                  "refuses every document whose target is not a rule's, and this list is the only "
                  "place they appear:" % (len(unplanned), " (list cut)" if more else ""))
            for relative in unplanned:
                print("  %s/" % relative)
        return 0

    proposed, refused = draft(rules, named_classes(os.path.join(REPO_ROOT, STATE)))
    if not proposed and not refused:
        print("Nothing to propose: every document class `%s` names is already covered by a rule "
              "(or the profile names none -- then the onboarding interview is what is missing, not "
              "this draft)." % os.path.join(STATE, PROFILE))
        return 0
    print("DRAFT -- a PROPOSAL, nothing is written. %d rule(s) for classes the plan does not cover."
          % len(proposed))
    print("Two structural choices are the manager's proposal and the user's to amend: a `%s` folder "
          "under each class, and the filename shape `%s`. The retention is NOT proposed -- it says "
          "`%s`, because a keeping period the kit chose would be one the user signs without "
          "deciding. REPLACE IT before you run either line: the kernel refuses a retention it "
          "cannot count in years, so a placeholder left standing stops the write instead of "
          "reaching the plan."
          % (YEAR_SEGMENT, FILENAME_TEMPLATE, RETENTION_QUESTION))
    print("\nThe tree this would produce:")
    for line in tree_lines([rule for rule, _what in proposed] + list(rules)):
        print("  " + line)
    for rule, what in proposed:
        print("\n%s -- %s" % (rule["id"], what or "(the owner named no words for this source)"))
        for line in _command_lines(rule, what):
            print(line)
    for one, what in refused:
        print("\nNOT PROPOSED: the class %r (from %r) cannot be used as it is spelled -- a "
              "class name is a FOLDER name AND a word on the command lines above, and only "
              "letters, digits, `_`, `-` and `.` are safe as both. Ask the user what the folder "
              "should be called; leaving it out keeps it visible as an uncovered source rather "
              "than filing it somewhere nobody meant." % (one, what))
    print("\nNothing has been written. Each rule needs the USER to answer the approval question "
          "first; `add-filing-rule` then writes exactly what they answered.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

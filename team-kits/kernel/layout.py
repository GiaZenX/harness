"""WHO writes what under the state directory -- one definition, several readers.

THE DEAD END THIS EXISTS TO END, measured 2026-08-02 in a scaffolded dev project: every write
route into `project_memory/` was refused with "only the kernel writes it", and for
`product/masterplan.md`, `project_config.yaml` and (office) `filing_plan.yaml` the kernel has no
writer and never will -- they are prose and configuration, not typed items. Meanwhile
`gate_memory_complete` blocks merge and push while the masterplan still carries its template line.
A gate whose condition no reachable operation can satisfy is not enforcement, it is a wall.

THE PROPERTY, not the three file names. The state directory holds two kinds of file:

  * CANONICAL STATE -- everything a KERNEL WRITER produces. Its name is composed by a kernel path
    builder out of a kernel-allocated id, its content goes through the status automaton, the
    approval hashes and the index. A tool write here really would bypass all three, and
    `approvals/pending/**` in particular holds mint codes in cleartext.
  * KIT DOCUMENTS -- the prose and configuration a kit ships into `templates/project_memory/`.
    No kernel path builder can name one, so no kernel command WRITES one as a file; they are
    ordinary project files that happen to live under the state directory, and they are scoped like
    ordinary project files.

    ONE QUALIFICATION, and it is a qualification and not an exception: a kernel command may write
    a DECLARED part of such a document. `set-preset` writes `project.preset` and nothing else in
    `project_config.yaml`, because the roles a project has installed had no writer at all and the
    only remaining route was a human with a text editor (BUG-0041); `add-filing-rule` APPENDS to
    `filing_plan.yaml`'s `rules` and touches nothing else, for the same reason one document over
    (FR-0049); and `kernel.documents` writes what a user-approved proposal ADDS to a document it
    can compare, which is the same reason again for every remaining one (BUG-0071). All write
    only what a USER minted an approval for. The document is still a document -- everything above
    about scoping and about tool writes is unchanged -- and `partial_writers` below is what lets a
    refusal say so instead of denying a route that exists. WHICH commands those are is asked of the
    writing modules, never counted here: this paragraph names three today and the sentence that
    counts them would be the one that rots.

`kernel_written_subtrees` answers the first half by ASKING THE WRITERS' OWN PATH BUILDERS with a
probe id, rather than by listing directories: `state.active_path`, `state.archive_path`,
`state.generated_path`, `approvals._request_path`, `dispatch._lease_path`,
`dispatch._envelope_path`, `staging.architecture_revisions_dir`. A writer that starts landing
somewhere new is a writer whose builder is asked here too.

That claim is MEASURED rather than asserted: `test_every_kernel_writer_lands_inside_the_declared
_area` in `tools/test_kernel.py` drives capture, freeze, lease, submit, mint, revoke, archive and
index regeneration in a real state directory and requires every file they create to answer
`is_kernel_written`. It goes red the day a writer lands outside, which is the only way this
module's definition can stay true.

WHAT IS DELIBERATELY NOT A DOCUMENT, and why the two exclusions are properties rather than names:
  * a DOTTED path segment -- `.kernel.lock`, `.audit/hook_events.jsonl`, `.gitkeep`. Nothing whose
    name begins with a dot is content a role writes; those are machinery, and the audit log in
    particular is the evidence the repeat-block escalation counts.
  * `staging/` -- spec II.4's explicitly non-canonical proposal area. It is not a document either:
    it has its OWN per-task-key rule in the write-scope gate, and answering "document" here would
    replace that rule with a weaker one.

THE SECOND HALF, added 2026-08-03: `gated_documents` -- WHICH of those documents is a WALL. A
document with no kernel writer is merely unusual; a document with no kernel writer that a
REGISTERED gate refuses work over is a state a project can install itself into and never leave from
inside a session. That derivation lived only in `tools/test_hooks.py`, which ships to no project, so
`doctor` -- the one tool whose job is to report the state -- said nothing about it (measured
2026-08-03: `grep -c "masterplan\\|filing_plan\\|project_config" kernel/report.py` = 0). It is here
because `report`, `_kernel` (the hooks' bridge) and that test are three readers of ONE answer.
"""
from __future__ import annotations

import ast
import os

from .backlog_types import ACTIVE_DIRS, format_id
from .state import STAGING_DIRNAME, ProjectState

# spec II.4's Vorschlagsbereich -- re-exported from `state`, which is where the directory's own
# builder composes it. This module compares a path SEGMENT (`is_project_document`) and so needs the
# name; the writers need the path, and one of the two spelling the other's answer is how a
# predicate and a writer come to disagree about a directory.
__all__ = ["STAGING_DIRNAME", "gated_documents", "is_in_proposal_area", "is_kernel_written",
           "is_project_document", "kernel_written_subtrees", "partial_writers",
           "path_segments_composed"]

# Probe values handed to the path builders. They name nothing that has to exist: a path builder
# composes a name, it does not open a file, so `TSK-0001` and a zero request id are enough to make
# every builder say WHERE it writes.
_PROBE_TASK_ID = "TSK-0001"
_PROBE_REQUEST_ID = "0" * 32
_PROBE_YEAR = 1970


def _relative(root: str, path: str) -> str:
    """`path` relative to the state root, lower-cased with forward slashes.

    Lower-cased because the FS on Windows and APFS are case-insensitive while a lexical
    comparison is not -- `gate_write_scope._norm` folds for exactly that reason, and a predicate
    that answered differently from the gate that calls it would be a hole with a docstring on it.
    """
    return os.path.relpath(path, root).replace("\\", "/").lower()


def kernel_written_subtrees(root: str) -> tuple:
    """Every state-relative DIRECTORY a kernel writer lands a file in, sorted.

    Asked of the builders themselves (see the module docstring). `root` only decides what the
    answers are made relative to; nothing here touches the disk.
    """
    # Local import: `approvals`, `dispatch` and `staging` all import `state`, and this module
    # imports them -- keeping it inside the call keeps the package's import graph a tree.
    from . import approvals, dispatch, scopes, staging

    state = ProjectState(root)
    # DIRECTORY builders answer with the directory itself; FILE builders answer with a file whose
    # dirname is taken below. `archive_root` is in the first group deliberately: `archive_path`
    # keys by type AND year, so a probe of it would declare `archive/pr/1970` canonical and leave
    # every real year outside.
    directories = {state.archive_root(), state.legacy_root(),
                   staging.architecture_revisions_dir(state),
                   staging.reports_dir(state)}
    paths = set()
    for item_type in ACTIVE_DIRS:
        probe = format_id(item_type, 1)
        paths.add(state.active_path(probe))
    paths.add(state.generated_path("index.yaml"))
    for flags in ({}, {"consumed": True}, {"revoked": True}):
        paths.add(approvals._request_path(state, _PROBE_REQUEST_ID, **flags))
    paths.add(dispatch._lease_path(state, _PROBE_TASK_ID))
    paths.add(dispatch._envelope_path(state, _PROBE_TASK_ID))
    paths.add(scopes._record_path(state, _PROBE_TASK_ID))
    directories.update(os.path.dirname(path) for path in paths)
    return tuple(sorted(_relative(state.root, directory) for directory in directories))


def is_kernel_written(root: str, relative_path: str) -> bool:
    """Does this state-relative path lie in an area a kernel writer produces?"""
    rel = str(relative_path or "").replace("\\", "/").strip("/").lower()
    if not rel:
        return True                       # the state directory itself is not a document
    for subtree in kernel_written_subtrees(root):
        if rel == subtree or rel.startswith(subtree + "/"):
            return True
    return False


def is_in_proposal_area(relative_path: str) -> bool:
    """Does this state-relative path lie in spec II.4's proposal area (`staging/`)?

    ONE ANSWER FOR EVERY READER OF IT, and it is here because two of them gave two. This predicate
    used to be a segment comparison written out wherever it was needed, and the copies did not fold
    case: `is_project_document` compared the LOWERED path (`_relative` folds, for the reason written
    there), `migrate._coverage_of` and `migrate.imported_legacy_ids` compared the path as the walk
    spelled it. Measured 2026-08-08 in a state holding `Staging/PR-0001/old_procs.yaml` -- one
    directory on this filesystem, two verdicts: the import's run-up called it SEARCHED while the
    document inventory (this function's caller) called it no document at all, so the dry run read
    it nowhere and named it nowhere, and the validator reported a V1 backlog record in it and
    refused the merge. The proposal area is the one place where that split is expensive in both
    directions: a body staged for capture carries an id and a status, so searching it reports every
    proposal as a V1 record, and NOT searching it silently hides a V1 store somebody moved there.

    The folding is the same one `_relative` does and the same one `gate_write_scope._norm` does, so
    what this refuses to search, what a role may write and what the gate scopes per task key are
    one answer about one directory.

    TWO RESIDUALS, AND THEY POINT OPPOSITE WAYS. On a case-sensitive filesystem a directory really
    named `Staging/` is a different directory there and is treated as the proposal area anyway --
    an over-exclusion, which costs a report rather than a refusal. The other way round, `str.lower`
    is not the folding a filesystem does: measured 2026-08-08 on this host, `staging.` opens the
    same directory as `staging` (and `staging..` opens nothing), while this predicate answers False
    for the first of the two -- so the fold agrees with the disk in case and not in this. Nothing
    reaches that today
    because every caller feeds it a name `os.walk` produced, and a walk produces the name the
    directory really has -- so it is a residual of the PREDICATE and not a hole in the harness. It
    is the entry `L29` in `docs/POST_V2_WISHLIST.md`.
    """
    rel = str(relative_path or "").replace("\\", "/").strip("/").lower()
    return bool(rel) and rel.split("/")[0] == STAGING_DIRNAME


# THE MODULES THAT WRITE ONE FIELD OF A KIT DOCUMENT, by name. An enumeration, and unavoidable:
# importing every module of the package to look for the attribute would pull the whole import graph
# into a hook's hot path, and the graph is a tree on purpose. It carries a tripwire that measures
# BOTH ends instead --
# `tools/test_kernel.py::test_every_kernel_module_that_writes_into_a_document_is_registered` walks
# the package for modules declaring `DOCUMENT_WRITES` and requires this tuple to be exactly them,
# so an entry that has stopped writing and a writer that never arrived here are one failure each.
_DOCUMENT_WRITER_MODULES = ("presets", "filing", "documents")

# The `document` value of a writer that owns no single named file. Such an entry carries `applies`
# -- the writing module's OWN predicate, `(state_root, relative_path) -> bool` -- and it decides
# per file, which is what keeps a generic route from being announced over documents it would then
# refuse. Named here because both sides read it: the writer declares it, `partial_writers` reads it.
ANY_DOCUMENT = "*"


def _document_writes() -> tuple:
    """Every declared (document, field, command) a kernel command writes -- asked of the writers."""
    import importlib                     # lazy: keeps the package's import graph a tree

    found = []
    for name in _DOCUMENT_WRITER_MODULES:
        module = importlib.import_module("." + name, __package__)
        found += list(getattr(module, "DOCUMENT_WRITES", ()))
    return tuple(found)


def partial_writers(relative_path: str, state_root: str = None) -> tuple:
    """({"field", "command"}, ...) a kernel COMMAND writes inside this kit document.

    Asked of the modules that do the writing (their own `DOCUMENT_WRITES`) rather than listed here,
    for the reason the module docstring gives: the refusal a role reads must not deny a route the
    harness has, and a second copy of "which command writes what" is how it would come to.
    Matched on the document's own path inside the state directory, case-folded like every other
    comparison in this module.

    `state_root` IS WHAT A GENERIC WRITER NEEDS AND A NAMED ONE DOES NOT. An entry for one named
    file is decided by its name alone, exactly as before. An entry declaring `ANY_DOCUMENT` is
    decided by the writer's own `applies` predicate, which reads the FILE -- `apply-proposal` can
    write a document it can compare and refuses one it cannot, and a route named for a file the
    command would refuse is the same broken promise as a route denied for one it would write.
    Without a root such an entry is left out: a caller that cannot say WHICH project it is asking
    about gets the answer that is certain, never a guess (`tools/test_kernel.py::
    test_a_generic_document_writer_is_named_only_for_the_documents_it_would_write`).
    """
    rel = str(relative_path or "").replace("\\", "/").strip("/").lower()
    found = []
    for entry in _document_writes():
        target = str(entry["document"])
        if target == ANY_DOCUMENT:
            applies = entry.get("applies")
            if state_root is None or applies is None or not applies(state_root, rel):
                continue
        elif target.lower() != rel:
            continue
        found.append({"field": entry["field"], "command": entry["command"]})
    return tuple(found)


def is_project_document(root: str, relative_path: str) -> bool:
    """Is this state-relative path a KIT DOCUMENT -- prose or config with no kernel writer?

    The complement of `is_kernel_written`, minus the two areas the module docstring names: a
    dotted segment is machinery and the proposal area has its own rule (`is_in_proposal_area`).
    """
    rel = str(relative_path or "").replace("\\", "/").strip("/").lower()
    if not rel:
        return False
    parts = rel.split("/")
    if any(part.startswith(".") for part in parts):
        return False
    if is_in_proposal_area(rel):
        return False
    return not is_kernel_written(root, rel)


# -- the walls: documents a REGISTERED gate refuses work over ------------------------------------

# How deep a name is followed back to the constants it was bound from. `MASTERPLAN =
# os.path.join("product", "masterplan.md")` is two levels; the bound is a cycle guard, not a
# judgement about how deep a hook may nest.
_BINDING_DEPTH = 4


def _module_bindings(tree: ast.Module) -> dict:
    """{name: value node} for every module-level `NAME = <expr>` with a single plain target.

    Module level only, and single-target only, because those are the bindings whose value is
    unambiguous without executing the file. A hook that composed its path out of a name assigned
    inside a function would not be followed -- see `path_segments_composed`.
    """
    bindings = {}
    for node in tree.body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)):
            bindings[node.targets[0].id] = node.value
    return bindings


def _is_path_join(node) -> bool:
    """Is this a `<something>.join(...)` whose receiver is not a string literal?

    `os.path.join(a, b)` composes a path; `", ".join(items)` composes a MESSAGE, and the
    difference between the two is the receiver. Excluding the literal-string receiver is what
    keeps the remedy prose of a gate -- which is full of `", ".join(sorted(...))` -- out of the
    answer below.
    """
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr == "join" and not isinstance(node.func.value, ast.Constant))


def path_segments_composed(tree: ast.Module) -> set:
    """Every string constant this module COMPOSES A FILESYSTEM PATH out of.

    THE SHARPENING, and it closes a residual that was named rather than fixed when this derivation
    still lived in the test suite. "A gate reads this file" used to mean "every segment of the
    file's path appears among the module's string constants ANYWHERE" -- so a name occurring only
    in a remedy sentence counted. Harmless in the direction it erred (a false wall costs a
    superfluous paragraph in the entry gates), but the reader added here is `doctor`, and a false
    wall in a state report is a sentence a user acts on.

    So a constant counts when it reaches the ARGUMENT of a path composition, directly or through a
    module-level name bound to a constant or to another composition. `PLAN = "filing_plan.yaml"`
    used as `os.path.join(state_dir(root), PLAN)` and `MASTERPLAN = os.path.join("product",
    "masterplan.md")` used as `os.path.join(state_dir(root), MASTERPLAN)` are the two shapes the
    shipped gates use, and both are covered by the rule rather than by naming them.

    THE LIMIT, and it errs the OTHER way, which is why it is stated instead of hidden: a hook that
    addresses a file by string concatenation, by `pathlib`, or through a name it binds inside a
    function is invisible here, and an invisible wall is a wall no report mentions. That direction
    is silence, not a false alarm, so it needs a tripwire rather than a caveat --
    `test_the_composed_path_rule_still_sees_every_document_a_gate_names` in `tools/test_hooks.py`
    compares this rule against the loose "constant anywhere" one over the shipped kits and goes red
    the day a hook starts addressing a document in a shape this cannot follow.
    """
    bindings = _module_bindings(tree)
    found = set()

    def harvest(node, depth=0):
        if depth > _BINDING_DEPTH:
            return
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            found.add(node.value)
        elif isinstance(node, ast.Name):
            bound = bindings.get(node.id)
            if bound is not None:
                harvest(bound, depth + 1)
        elif _is_path_join(node):
            for argument in node.args:
                harvest(argument, depth + 1)

    for node in ast.walk(tree):
        if _is_path_join(node):
            for argument in node.args:
                harvest(argument)
    return found


def _can_refuse(tree: ast.Module) -> bool:
    """Does this module call `<something>.block(...)`, i.e. can it REFUSE an operation?

    Read from the AST rather than from a `gate_`/`guard_` name prefix, because that prefix is a
    convention: `session_status` names two of these documents and refuses nothing, and
    `guard_fs_tripwire` refuses plenty.
    """
    return any(isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
               and node.func.attr == "block" for node in ast.walk(tree))


def gated_documents(repo_root: str, state_root: str) -> dict:
    """{document path relative to `state_root`: {"hook", "audit_name"}} -- the WALLS.

    A wall is a KIT DOCUMENT (`is_project_document`: no kernel writer can name it) whose content a
    REGISTERED, refusal-capable hook of this installation reads. Both halves are load-bearing:
    without the first, the answer includes files a `harness.py` command fills; without the second,
    it includes documents nobody blocks on, and `master_data.yaml` and `business_profile.yaml` --
    writer-less office documents no gate reads -- correctly fall out for exactly that reason.

    Registration is `report._wired_hooks`, which already knows the ways a registration cannot fire
    (wrong matcher, non-command type, missing file, an exit code the wrapper swallows); a hook that
    ships and is wired nowhere refuses nothing. `audit_name` is the hook's own `HOOK` constant --
    the name it records blocks under, so a reader can count what this gate actually refused.

    NOTHING IS EXECUTED HERE. The hooks are parsed, not imported: this runs inside `doctor`, which
    is the tool of last resort, and importing a kit hook installs `_kernel`'s exit-2 excepthook into
    the reporting process. Asking a gate for its own verdict is a separate step and belongs on the
    hook side, where that import is already the normal state -- see `_kernel.unfilled_gated_documents`.
    """
    from . import report                # lazy: keeps the package's import graph a tree

    hooks_dir = os.path.join(repo_root, ".claude", "hooks")
    if not os.path.isdir(hooks_dir):
        return {}
    documents = []
    for dirpath, _dirs, files in os.walk(state_root):
        for name in sorted(files):
            rel = os.path.relpath(os.path.join(dirpath, name), state_root).replace(os.sep, "/")
            if is_project_document(state_root, rel):
                documents.append(rel)
    found = {}
    for name in sorted(report._wired_hooks(repo_root)):
        try:
            with open(os.path.join(hooks_dir, name), encoding="utf-8") as handle:
                tree = ast.parse(handle.read(), filename=name)
        except (OSError, SyntaxError, ValueError):
            # a hook that does not parse enforces nothing this function can describe; the
            # installation defect itself is `doctor`'s bundle/trust business, not this one's
            continue
        if not _can_refuse(tree):
            continue
        composed = path_segments_composed(tree)
        audit = _module_bindings(tree).get("HOOK")
        audit_name = (audit.value if isinstance(audit, ast.Constant)
                      and isinstance(audit.value, str) else name)
        for rel in documents:
            if all(segment in composed for segment in rel.split("/")):
                found[rel] = {"hook": name, "audit_name": audit_name}
    return found

#!/usr/bin/env python3
"""
PostToolUse(Edit|Write) — validate a project_memory/*.yaml IMMEDIATELY after it is written.

A real run shipped decisions.yaml/architecture.yaml as invalid YAML repeatedly: the architect (a
spec-writing role without Bash) could not parse-check its own artifacts, the dashboard generator
swallowed the error silently, and a pipeline lint only catches it at MERGE time — after which a
different role had to hot-fix another owner's file. This hook closes the loop at WRITE time: the
moment any role writes broken YAML (parse error OR duplicate key — safe_load silently keeps the
last duplicate), it gets the exact error back and fixes its OWN file on the spot.

Parsing uses yaml.safe_load only; duplicate keys are found by walking yaml.compose()'s node graph
(compose builds nodes, never constructs objects — no code-execution surface). Claude receives an
exit-2 correction; Codex receives a PostToolUse `decision: block` response. Defensive: not a
project_memory yaml / no PyYAML / internal error -> exit 0.

Also the format backstop for progress.yaml: a real PM regrew `status` into a 307-line blob and
dropped `log:` although the template says "ONE line" — prompt-level rules the PM applies to itself
get ignored, so the artifact's own contract is enforced here mechanically.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _compat

YAML_TIPS = ("Tips: put prose containing ':' in a block scalar (key: |), quote strings with special "
             "characters, and never repeat a key at the same level.")


def block(base, msg, why="is INVALID YAML after your edit", tips=YAML_TIPS):
    if len(msg) > 600:
        msg = msg[:600] + " …"
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import _audit
        _audit.record("guard_yaml_valid", base)
    except Exception:
        pass
    message = (
        "[team-kit guard] project_memory/%s %s:\n%s\n"
        "Fix it NOW — you own this artifact. %s Do not hand the file to another role; "
        "do not leave it broken.\n" % (base, why, msg, tips)
    )
    _compat.stop(message, "PostToolUse")


def find_duplicate_keys(yaml_mod, text):
    """Walk the composed node graph (no object construction) and collect duplicate mapping keys."""
    dupes = []
    try:
        root = yaml_mod.compose(text, Loader=yaml_mod.SafeLoader)
    except Exception:
        return dupes  # parse problems are reported by safe_load already
    stack = [root] if root is not None else []
    visited = set()  # anchors/aliases make the node graph cyclic — never walk a node twice
    while stack:
        node = stack.pop()
        if id(node) in visited:
            continue
        visited.add(id(node))
        if isinstance(node, yaml_mod.MappingNode):
            seen = set()
            for k, v in node.value:
                if isinstance(k, yaml_mod.ScalarNode):
                    if k.value in seen:
                        dupes.append("duplicate key %r (line %d) — safe_load silently keeps only "
                                     "the last one" % (k.value, k.start_mark.line + 1))
                    seen.add(k.value)
                stack.append(k)
                stack.append(v)
        elif isinstance(node, yaml_mod.SequenceNode):
            stack.extend(node.value)
    return dupes


def progress_format_problems(data):
    """progress.yaml contract (V10 backstop): `status` stays ONE line (state + next action); history
    lives in the append-only `log:` list. Returns problem strings, empty when compliant."""
    if not isinstance(data, dict):
        return []
    problems = []
    status = data.get("status")
    if isinstance(status, str):
        lines = [ln for ln in status.splitlines() if ln.strip()]
        if len(lines) > 3 or len(status) > 700:
            problems.append(
                "`status` is %d non-empty lines / %d chars — it MUST stay ONE line: current state + the "
                "concrete next action. Move history/details into the append-only `log:` list (a real run's "
                "300-line status blob caused giant re-edits, token burn and tool-call parse failures)."
                % (len(lines), len(status)))
    if "log" not in data:
        problems.append(
            "the append-only `log:` list is missing — keep a `log:` key (even empty: `log: []`); dated "
            "one-line history entries belong there, NEVER in `status`.")
    return problems


def check(path):
    norm = path.replace("\\", "/")
    base = os.path.basename(norm)
    if "project_memory" not in norm.split("/") or not base.endswith((".yaml", ".yml")):
        return
    if not os.path.isfile(path):
        return

    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError:
        return  # no parser available here; the pipeline yaml-lint still catches it in CI

    try:
        with open(path, encoding="utf-8", errors="ignore") as fh:
            text = fh.read()
    except Exception:
        return

    data_y = None
    try:
        data_y = yaml.safe_load(text)
    except yaml.YAMLError as e:
        block(base, str(e))
    except Exception:
        return  # internal edge case — never block on our own bug

    dupes = find_duplicate_keys(yaml, text)
    if dupes:
        block(base, "\n".join(dupes))

    if base == "progress.yaml":
        problems = progress_format_problems(data_y)
        if problems:
            block(base, "\n".join(problems), why="violates its format contract after your edit",
                  tips="See the header comments in the shipped progress.yaml template.")


def main():
    data = _compat.load()
    if data.get("tool_name") not in ("Edit", "Write", "MultiEdit"):
        sys.exit(0)
    for path in _compat.file_paths(data):
        check(path)
    sys.exit(0)


if __name__ == "__main__":
    main()

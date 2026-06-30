#!/usr/bin/env python3
"""
generate_dashboard.py - owned by: PM (generated artifact source)  [research-team]

Deterministically renders progress.dashboard.html from the project_memory YAML
files. The agents run this script at the end of every phase instead of editing
the dashboard by hand, so the dashboard is always in sync and costs zero tokens.

What it does:
  1. Reads research_questions.yaml, tasks.yaml, protocol_amendments.yaml,
     progress.yaml (all siblings of this script).
  2. Builds the dashboard data model (per-item lists with owner, origin and
     start/end dates) and computes the diff against the previous run.
  3. Archives the current progress.dashboard.html into dashboard_history/
     (timestamped) before overwriting it.
  4. Renders a fresh progress.dashboard.html from progress.dashboard.template.html.
  5. Saves a state snapshot for the next diff.

Dependency: PyYAML (pip install pyyaml). The GENERATED html stays
dependency-free and opens by double-click; PyYAML is only needed to run this
build step.

Usage:
  python generate_dashboard.py
"""

import datetime
import json
import os
import re
import sys

try:
    import yaml  # type: ignore[import-untyped]
except ImportError:
    sys.stderr.write(
        "PyYAML is required to generate the dashboard.\n"
        "Install it once with:  pip install pyyaml\n"
    )
    sys.exit(1)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(BASE_DIR, "progress.dashboard.template.html")
OUTPUT = os.path.join(BASE_DIR, "progress.dashboard.html")
HISTORY_DIR = os.path.join(BASE_DIR, "dashboard_history")
STATE_FILE = os.path.join(HISTORY_DIR, ".dashboard_state.json")

RQ_ORDER = ["proposed", "approved", "investigated", "validated", "accepted", "rejected"]
TASK_ORDER = ["todo", "in_progress", "done", "validated", "rejected"]
PA_ORDER = ["open", "applied", "rejected"]

# Protocol amendments collapse several raw statuses into the "open" bucket.
PA_STATUS_MAP = {
    "PROPOSED": "open",
    "WAITING_APPROVAL": "open",
    "APPROVED": "open",
    "APPLIED": "applied",
    "REJECTED": "rejected",
}

# Statuses that count a research question as "delivered" for roadmap progress.
DONE_STATUSES = {"validated", "accepted", "done", "applied"}


def load_yaml(name):
    """Load a sibling YAML file, returning {} on missing/empty/invalid."""
    path = os.path.join(BASE_DIR, name)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except yaml.YAMLError as exc:
        sys.stderr.write("Could not parse %s: %s\n" % (name, exc))
        return {}
    return data or {}


def as_str(value):
    return "" if value is None else str(value)


def join_list(value):
    if isinstance(value, (list, tuple)):
        return ", ".join(str(v) for v in value)
    return as_str(value)


def build_research_questions():
    raw = load_yaml("research_questions.yaml").get("research_questions") or {}
    items = []
    for rid, body in raw.items():
        body = body or {}
        status = as_str(body.get("status")).upper()
        items.append({
            "id": rid,
            "title": as_str(body.get("title")),
            "status": status.lower() if status else "proposed",
            "raw_status": status or "PROPOSED",
            "owner": "",
            "origin": "",
            "start": as_str(body.get("created")),
            "end": as_str(body.get("closed")),
        })
    items.sort(key=lambda x: x["id"])
    return items


def build_tasks():
    raw = load_yaml("tasks.yaml").get("tasks") or {}
    items = []
    for tid, body in raw.items():
        body = body or {}
        status = as_str(body.get("status")).upper()
        items.append({
            "id": tid,
            "title": as_str(body.get("title")),
            "status": status.lower() if status else "todo",
            "raw_status": status or "TODO",
            "owner": as_str(body.get("owner")),
            "origin": as_str(body.get("derives_from")),
            "start": as_str(body.get("created")),
            "end": as_str(body.get("completed")),
        })
    items.sort(key=lambda x: x["id"])
    return items


def build_protocol_amendments():
    raw = load_yaml("protocol_amendments.yaml").get("protocol_amendments") or {}
    items = []
    for pid, body in raw.items():
        body = body or {}
        status = as_str(body.get("status")).upper()
        canonical = PA_STATUS_MAP.get(status, "open")
        items.append({
            "id": pid,
            "title": as_str(body.get("description")),
            "status": canonical,
            "raw_status": status or "PROPOSED",
            "owner": "",
            "origin": join_list(body.get("affects")),
            "start": as_str(body.get("created")),
            "end": as_str(body.get("applied")),
        })
    items.sort(key=lambda x: x["id"])
    return items


def build_milestones(items_by_id):
    """Roadmap view: each milestone groups research-question ids; progress = delivered / total."""
    raw = load_yaml("progress.yaml").get("milestones") or []
    out = []
    for ms in raw:
        ms = ms or {}
        ids = [str(i) for i in (ms.get("items") or [])]
        members, done = [], 0
        for iid in ids:
            it = items_by_id.get(iid)
            st = it["status"] if it else ""
            if st in DONE_STATUSES:
                done += 1
            members.append({"id": iid, "status": st, "title": it["title"] if it else ""})
        out.append({
            "id": as_str(ms.get("id")),
            "title": as_str(ms.get("title")),
            "target": as_str(ms.get("target")),
            "total": len(ids),
            "done": done,
            "items": members,
        })
    return out


def strip_internal(items):
    """Return items without the raw_status helper field (not needed in the UI)."""
    clean = []
    for it in items:
        clean.append({k: v for k, v in it.items() if k != "raw_status"})
    return clean


def load_state():
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as fh:
            return json.load(fh) or {}
    except (ValueError, OSError):
        return {}


def compute_changes(all_items, prior):
    """Diff current raw statuses against the prior snapshot."""
    new_items, changed_items = [], []
    for it in all_items:
        before = prior.get(it["id"])
        if before is None:
            new_items.append({
                "kind": "new",
                "id": it["id"],
                "title": it["title"],
                "to": it["raw_status"],
            })
        elif before != it["raw_status"]:
            changed_items.append({
                "kind": "changed",
                "id": it["id"],
                "title": it["title"],
                "from": before,
                "to": it["raw_status"],
            })
    new_items.sort(key=lambda x: x["id"])
    changed_items.sort(key=lambda x: x["id"])
    return new_items + changed_items


def archive_current():
    """Move the existing dashboard into dashboard_history/ with a timestamp."""
    if not os.path.exists(OUTPUT):
        return
    if not os.path.isdir(HISTORY_DIR):
        os.makedirs(HISTORY_DIR)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = os.path.join(HISTORY_DIR, "progress.dashboard.%s.html" % stamp)
    os.replace(OUTPUT, dest)


def render(data):
    with open(TEMPLATE, "r", encoding="utf-8") as fh:
        template = fh.read()
    block = json.dumps(data, indent=2, ensure_ascii=False)
    replacement = (
        '<script type="application/json" id="dashboard-data">\n'
        + block
        + "\n</script>"
    )
    pattern = re.compile(
        r'<script type="application/json" id="dashboard-data">.*?</script>',
        re.DOTALL,
    )
    if not pattern.search(template):
        sys.stderr.write("Template is missing the dashboard-data block.\n")
        sys.exit(1)
    return pattern.sub(lambda _m: replacement, template, count=1)


def main():
    if not os.path.exists(TEMPLATE):
        sys.stderr.write("Template not found: %s\n" % TEMPLATE)
        sys.exit(1)

    research_questions = build_research_questions()
    tasks = build_tasks()
    protocol_amendments = build_protocol_amendments()
    all_items = research_questions + tasks + protocol_amendments

    prior = load_state()
    changes = compute_changes(all_items, prior)

    items_by_id = {it["id"]: it for it in research_questions}
    roadmap = build_milestones(items_by_id)

    progress = load_yaml("progress.yaml")
    status_text = as_str(progress.get("status"))
    today = datetime.date.today().isoformat()

    data = {
        "status": status_text,
        "last_update": today,
        "research_questions": {"order": RQ_ORDER, "items": strip_internal(research_questions)},
        "tasks": {"order": TASK_ORDER, "items": strip_internal(tasks)},
        "protocol_amendments": {"order": PA_ORDER, "items": strip_internal(protocol_amendments)},
        "roadmap": roadmap,
        "changes": changes,
    }

    html = render(data)

    archive_current()
    with open(OUTPUT, "w", encoding="utf-8") as fh:
        fh.write(html)

    if not os.path.isdir(HISTORY_DIR):
        os.makedirs(HISTORY_DIR)
    snapshot = {it["id"]: it["raw_status"] for it in all_items}
    with open(STATE_FILE, "w", encoding="utf-8") as fh:
        json.dump(snapshot, fh, indent=2, ensure_ascii=False)

    sys.stdout.write(
        "Dashboard generated: %s (%d research questions, %d tasks, %d PAs, %d milestones, %d changes)\n"
        % (OUTPUT, len(research_questions), len(tasks), len(protocol_amendments), len(roadmap), len(changes))
    )


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
generate_dashboard.py - owned by: PM (generated artifact source)

Deterministically renders progress.dashboard.html from the project_memory YAML
files. The agents run this script at the end of every phase instead of editing
the dashboard by hand, so the dashboard is always in sync and costs zero tokens.

What it does:
  1. Reads product_requirements.yaml, tasks.yaml, change_requests.yaml,
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

REQ_ORDER = ["proposed", "approved", "done", "tested", "accepted", "rejected"]
TASK_ORDER = ["todo", "in_progress", "done", "validated", "rejected"]
CR_ORDER = ["open", "applied", "rejected"]

# Change requests collapse several raw statuses into the "open" bucket.
CR_STATUS_MAP = {
    "PROPOSED": "open",
    "WAITING_APPROVAL": "open",
    "APPROVED": "open",
    "APPLIED": "applied",
    "REJECTED": "rejected",
}


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


def build_requirements():
    raw = load_yaml("product_requirements.yaml").get("requirements") or {}
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


def build_change_requests():
    raw = load_yaml("change_requests.yaml").get("change_requests") or {}
    items = []
    for cid, body in raw.items():
        body = body or {}
        status = as_str(body.get("status")).upper()
        canonical = CR_STATUS_MAP.get(status, "open")
        items.append({
            "id": cid,
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

    requirements = build_requirements()
    tasks = build_tasks()
    change_requests = build_change_requests()
    all_items = requirements + tasks + change_requests

    prior = load_state()
    changes = compute_changes(all_items, prior)

    progress = load_yaml("progress.yaml")
    status_text = as_str(progress.get("status"))
    today = datetime.date.today().isoformat()

    data = {
        "status": status_text,
        "last_update": today,
        "requirements": {"order": REQ_ORDER, "items": strip_internal(requirements)},
        "tasks": {"order": TASK_ORDER, "items": strip_internal(tasks)},
        "change_requests": {"order": CR_ORDER, "items": strip_internal(change_requests)},
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
        "Dashboard generated: %s (%d requirements, %d tasks, %d CRs, %d changes)\n"
        % (OUTPUT, len(requirements), len(tasks), len(change_requests), len(changes))
    )


if __name__ == "__main__":
    main()

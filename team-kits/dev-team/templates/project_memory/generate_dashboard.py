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
FR_ORDER = ["proposed", "triaged", "accepted", "deferred", "rejected"]
BUG_ORDER = ["open", "in_progress", "fixed", "verified", "wontfix"]

# Bug raw statuses map onto the defect buckets (DUPLICATE folds into the closed-without-fix bucket).
BUG_STATUS_MAP = {
    "OPEN": "open",
    "IN_PROGRESS": "in_progress",
    "FIXED": "fixed",
    "VERIFIED": "verified",
    "WONTFIX": "wontfix",
    "DUPLICATE": "wontfix",
}

# Change requests collapse several raw statuses into the "open" bucket.
CR_STATUS_MAP = {
    "PROPOSED": "open",
    "WAITING_APPROVAL": "open",
    "APPROVED": "open",
    "APPLIED": "applied",
    "REJECTED": "rejected",
}

# Feature-request raw statuses map onto the backlog buckets.
FR_STATUS_MAP = {
    "PROPOSED": "proposed",
    "TRIAGED": "triaged",
    "ACCEPTED": "accepted",
    "DEFERRED": "deferred",
    "REJECTED": "rejected",
}

# Statuses that count a requirement / feature as "delivered" for roadmap progress.
DONE_STATUSES = {"done", "tested", "accepted", "applied", "validated"}


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


def build_feature_requests():
    raw = load_yaml("feature_requests.yaml").get("feature_requests") or {}
    items = []
    for fid, body in raw.items():
        body = body or {}
        status = as_str(body.get("status")).upper()
        canonical = FR_STATUS_MAP.get(status, "proposed")
        items.append({
            "id": fid,
            "title": as_str(body.get("title")) or as_str(body.get("user_story")),
            "status": canonical,
            "raw_status": status or "PROPOSED",
            "owner": as_str(body.get("priority")),          # MoSCoW priority shown as the "owner" chip
            "origin": as_str(body.get("becomes")),          # the PRD it was triaged into, if any
            "start": as_str(body.get("created")),
            "end": as_str(body.get("closed")),
        })
    items.sort(key=lambda x: x["id"])
    return items


def build_bugs():
    raw = load_yaml("bugs.yaml").get("bugs") or {}
    items = []
    for bid, body in raw.items():
        body = body or {}
        status = as_str(body.get("status")).upper()
        canonical = BUG_STATUS_MAP.get(status, "open")
        items.append({
            "id": bid,
            "title": as_str(body.get("title")),
            "status": canonical,
            "raw_status": status or "OPEN",
            "owner": as_str(body.get("severity")),          # severity shown as the chip
            "origin": join_list(body.get("violates")),      # the PRD/SR it breaks
            "start": as_str(body.get("created")),
            "end": as_str(body.get("closed")),
        })
    items.sort(key=lambda x: x["id"])
    return items


def build_milestones(items_by_id):
    """Roadmap view: each milestone groups requirement/feature ids; progress = delivered / total."""
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

    requirements = build_requirements()
    tasks = build_tasks()
    change_requests = build_change_requests()
    feature_requests = build_feature_requests()
    bugs = build_bugs()
    all_items = requirements + tasks + change_requests + feature_requests + bugs

    prior = load_state()
    changes = compute_changes(all_items, prior)

    items_by_id = {it["id"]: it for it in (requirements + feature_requests)}
    roadmap = build_milestones(items_by_id)

    progress = load_yaml("progress.yaml")
    status_text = as_str(progress.get("status"))
    today = datetime.date.today().isoformat()

    data = {
        "status": status_text,
        "last_update": today,
        "requirements": {"order": REQ_ORDER, "items": strip_internal(requirements)},
        "tasks": {"order": TASK_ORDER, "items": strip_internal(tasks)},
        "change_requests": {"order": CR_ORDER, "items": strip_internal(change_requests)},
        "feature_requests": {"order": FR_ORDER, "items": strip_internal(feature_requests)},
        "bugs": {"order": BUG_ORDER, "items": strip_internal(bugs)},
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
        "Dashboard generated: %s (%d requirements, %d tasks, %d CRs, %d FRs, %d bugs, %d milestones, "
        "%d changes)\n"
        % (OUTPUT, len(requirements), len(tasks), len(change_requests),
           len(feature_requests), len(bugs), len(roadmap), len(changes))
    )


if __name__ == "__main__":
    main()

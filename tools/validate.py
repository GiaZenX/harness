#!/usr/bin/env python3
"""
validate.py — structural self-check for the agents-and-skills repo (dogfooding).

Compiles every shipped hook/script, parses every YAML (templates, registry, agent + skill frontmatter)
and JSON (kit settings), and checks the wiring: each agent's `skills:` resolve to a skill dir, and every
registry role has an agent file. Exit 1 on any failure. Run locally or in CI: python tools/validate.py
"""
import glob
import json
import os
import py_compile
import sys

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
fails = []


def rel(p):
    return os.path.relpath(p, ROOT).replace("\\", "/")


def frontmatter(text):
    if not text.startswith("---"):
        return None
    return yaml.safe_load(text.split("---", 2)[1])


# 1) compile python
for p in glob.glob(ROOT + "/team-kits/**/hooks/*.py", recursive=True) + \
         glob.glob(ROOT + "/team-kits/**/templates/repo/scripts/*.py", recursive=True) + \
         glob.glob(ROOT + "/tools/*.py"):
    try:
        py_compile.compile(p, doraise=True)
    except Exception as e:
        fails.append("compile %s: %s" % (rel(p), e))

# 2) parse YAML (templates + registry)
for p in glob.glob(ROOT + "/team-kits/**/templates/project_memory/*.yaml", recursive=True) + \
         [ROOT + "/team-kits/registry.yaml"]:
    try:
        yaml.safe_load(open(p, encoding="utf-8").read())
    except Exception as e:
        fails.append("yaml %s: %s" % (rel(p), e))

# 3) parse kit settings.json
for p in glob.glob(ROOT + "/team-kits/*/settings/settings.json"):
    try:
        json.load(open(p, encoding="utf-8"))
    except Exception as e:
        fails.append("json %s: %s" % (rel(p), e))

# 4) agent frontmatter + skills wiring
for p in glob.glob(ROOT + "/team-kits/**/agents/*.md", recursive=True):
    fm = None
    try:
        fm = frontmatter(open(p, encoding="utf-8").read())
    except Exception as e:
        fails.append("frontmatter %s: %s" % (rel(p), e))
        continue
    if not fm:
        continue
    kit_dir = os.path.dirname(os.path.dirname(p))
    for sk in (fm.get("skills") or []):
        if not os.path.isdir(os.path.join(kit_dir, "skills", sk)):
            fails.append("%s: skills:[%s] has no skill dir" % (rel(p), sk))

# 5) skill frontmatter
for p in glob.glob(ROOT + "/team-kits/**/skills/**/SKILL.md", recursive=True):
    try:
        frontmatter(open(p, encoding="utf-8").read())
    except Exception as e:
        fails.append("skill frontmatter %s: %s" % (rel(p), e))

# 6) registry roles -> agent files exist
reg = yaml.safe_load(open(ROOT + "/team-kits/registry.yaml", encoding="utf-8").read())
for team in reg.get("teams", []):
    kit = team["key"]
    for role in team.get("roles", []):
        if not os.path.isfile(ROOT + "/team-kits/%s/agents/%s.md" % (kit, role)):
            fails.append("registry: %s role '%s' has no agent file" % (kit, role))

# 7) model_map/effort_map <-> specialist agent frontmatter (catch tier drift in the shipped kit)
for cfg in glob.glob(ROOT + "/team-kits/*/templates/project_memory/project_config.yaml"):
    kit_dir = os.path.dirname(os.path.dirname(os.path.dirname(cfg)))   # -> team-kits/<kit>
    try:
        conf = yaml.safe_load(open(cfg, encoding="utf-8").read()) or {}
    except Exception:
        continue  # YAML parse already reported in step 2
    lead = "project-manager"  # the session lead is excluded from the maps
    sp = os.path.join(kit_dir, "settings", "settings.json")
    if os.path.isfile(sp):
        try:
            lead = json.load(open(sp, encoding="utf-8")).get("agent") or lead
        except Exception:
            pass
    specialists = {os.path.splitext(os.path.basename(a))[0]
                   for a in glob.glob(os.path.join(kit_dir, "agents", "*.md"))} - {lead}
    field_of = {"model_map": "model", "effort_map": "effort"}
    for mapname, field in field_of.items():
        m = conf.get(mapname) or {}
        keys = set(m)
        for missing in sorted(specialists - keys):
            fails.append("%s: %s missing specialist '%s'" % (rel(cfg), mapname, missing))
        for stray in sorted(keys - specialists):
            fails.append("%s: %s has key '%s' with no matching agent" % (rel(cfg), mapname, stray))
        if lead in keys:
            fails.append("%s: %s must NOT list the session lead '%s'" % (rel(cfg), mapname, lead))
        # each specialist MUST carry the field, and it must equal the map value
        for role in sorted(specialists):
            ap = os.path.join(kit_dir, "agents", role + ".md")
            try:
                afm = frontmatter(open(ap, encoding="utf-8").read()) or {}
            except Exception:
                continue
            if field not in afm:
                fails.append("%s: specialist missing '%s:' frontmatter" % (rel(ap), field))
            elif role in keys and str(afm[field]) != str(m[role]):
                fails.append("%s: %s:%s != %s '%s' (%s)" % (rel(ap), field, afm[field], mapname, m[role], role))
    # the session lead carries model: + effort: but is NOT in the maps
    lp = os.path.join(kit_dir, "agents", lead + ".md")
    if os.path.isfile(lp):
        lfm = frontmatter(open(lp, encoding="utf-8").read()) or {}
        for field in ("model", "effort"):
            if field not in lfm:
                fails.append("%s: session lead missing '%s:' frontmatter" % (rel(lp), field))

# 8) kit VERSION stamps must match the kit content (forgetting a bump is a CI failure), and the
#    constitution marker must sit on line 1 (session_status parses only the first line for the kit key —
#    if it ever moved, update detection would go blind silently).
sys.path.insert(0, os.path.join(ROOT, "tools"))
from bump_kit_version import discover_kits, kit_hash  # noqa: E402

for kit in discover_kits(ROOT):
    kit_dir = os.path.join(ROOT, "team-kits", kit)
    vfile = os.path.join(kit_dir, "VERSION")
    if not os.path.isfile(vfile):
        fails.append("%s: missing team-kits/%s/VERSION — run python tools/bump_kit_version.py" % (kit, kit))
    elif ("content: %s" % kit_hash(kit_dir)) not in open(vfile, encoding="utf-8").read():
        fails.append("%s: kit files changed but VERSION not bumped — run python tools/bump_kit_version.py" % kit)
    cpath = os.path.join(kit_dir, "constitution", "CLAUDE.md")
    if os.path.isfile(cpath):
        lines = open(cpath, encoding="utf-8", errors="ignore").read().splitlines()
        if not lines or "agents-and-skills:team-kit" not in lines[0]:
            fails.append("%s: constitution marker not on LINE 1 — session_status kit-update detection "
                         "reads only the first line" % kit)
        # context diet (official guidance: bloated CLAUDE.md files get ignored; the constitution
        # loads into the PM AND every subagent spawn — verified empirically 2026-07-14)
        if len(lines) > 220:
            fails.append("%s: constitution has %d lines (> 220) — keep the core slim; move role "
                         "mechanics into the role SKILLs (they load only for the affected role)"
                         % (kit, len(lines)))

# 9) intended-identical hooks/scripts must stay byte-identical across kits (audit finding: a fix
#    applied in one kit silently diverges the others — exactly the drift class this repo hunts).
MIRROR_DEV_RESEARCH = [
    "hooks/guard_yaml_valid.py", "hooks/guard_agent_spawn.py", "hooks/notify_agent_events.py",
    "hooks/guard_scratchpad_ref.py", "hooks/gate_subagent_output.py", "hooks/guard_harness_selfmod.py",
    "hooks/_root.py", "hooks/_audit.py", "hooks/auto_dashboard.py",
    "templates/repo/scripts/quality.py", "templates/repo/scripts/kit_checks.py",
    "templates/repo/scripts/retro.py",
]
MIRROR_DEV_OFFICE = [
    "hooks/guard_yaml_valid.py", "hooks/guard_agent_spawn.py", "hooks/notify_agent_events.py",
    "hooks/guard_scratchpad_ref.py", "hooks/gate_subagent_output.py", "hooks/guard_harness_selfmod.py",
    "hooks/_root.py", "hooks/_audit.py",
]
for other, names in (("research-team", MIRROR_DEV_RESEARCH), ("office-team", MIRROR_DEV_OFFICE)):
    for name in names:
        a = os.path.join(ROOT, "team-kits", "dev-team", name)
        b = os.path.join(ROOT, "team-kits", other, name)
        if not (os.path.isfile(a) and os.path.isfile(b)):
            fails.append("mirror: %s missing in dev-team or %s" % (name, other))
        elif open(a, "rb").read() != open(b, "rb").read():
            fails.append("mirror: %s diverged between dev-team and %s — copy the fixed file" % (name, other))

# 10) every §-reference in hooks/skills/agents must resolve to a heading (## N.) or a bold anchor
#     (**Na.) in that kit's constitution — a block message citing a deleted paragraph teaches
#     the agent to look for nothing (audit finding after the constitution diet).
import re as _re  # noqa: E402
for kit_dir_name in os.listdir(os.path.join(ROOT, "team-kits")):
    cpath = os.path.join(ROOT, "team-kits", kit_dir_name, "constitution", "CLAUDE.md")
    if not os.path.isfile(cpath):
        continue
    cons = open(cpath, encoding="utf-8", errors="ignore").read()
    anchors = set(_re.findall(r"(?m)^##+\s*(\d+[a-z]?)\.", cons))
    anchors |= set(_re.findall(r"(?m)^\*\*(\d+[a-z]?)\.", cons))
    for pattern in ("hooks/*.py", "skills/*/SKILL.md", "agents/*.md"):
        for p in glob.glob(os.path.join(ROOT, "team-kits", kit_dir_name, pattern)):
            txt = open(p, encoding="utf-8", errors="ignore").read()
            for m in _re.finditer(r"§(\d+[a-z]?)", txt):
                if txt[m.end():m.end() + 1] == ".":
                    continue  # §2.7-style sub-reference resolves to its parent section
                if m.group(1) not in anchors:
                    fails.append("%s: references §%s which does not exist in %s's constitution"
                                 % (rel(p), m.group(1), kit_dir_name))
                    break  # one finding per file is enough

if fails:
    print("VALIDATION FAILED (%d):" % len(fails))
    for f in fails:
        print("  - " + f)
    sys.exit(1)
print("validate.py: all structural checks passed.")

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

if fails:
    print("VALIDATION FAILED (%d):" % len(fails))
    for f in fails:
        print("  - " + f)
    sys.exit(1)
print("validate.py: all structural checks passed.")

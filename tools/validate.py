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
        # each specialist's frontmatter field must equal the map value
        for role in sorted(specialists & keys):
            ap = os.path.join(kit_dir, "agents", role + ".md")
            try:
                afm = frontmatter(open(ap, encoding="utf-8").read()) or {}
            except Exception:
                continue
            got = afm.get(field)
            if got is not None and str(got) != str(m[role]):
                fails.append("%s: %s:%s != %s '%s' (%s)" % (rel(ap), field, got, mapname, m[role], role))
    # the session lead carries model: + effort: but is NOT in the maps
    lp = os.path.join(kit_dir, "agents", lead + ".md")
    if os.path.isfile(lp):
        lfm = frontmatter(open(lp, encoding="utf-8").read()) or {}
        for field in ("model", "effort"):
            if field not in lfm:
                fails.append("%s: session lead missing '%s:' frontmatter" % (rel(lp), field))

if fails:
    print("VALIDATION FAILED (%d):" % len(fails))
    for f in fails:
        print("  - " + f)
    sys.exit(1)
print("validate.py: all structural checks passed.")
